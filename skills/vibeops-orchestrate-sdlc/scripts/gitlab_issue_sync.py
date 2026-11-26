"""Synchronize a requirements-agent handoff to GitLab."""
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
from issue_state import scheduler_lock
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'shared/python'))
import httpx
from credential_store import resolve
from itsm_handoff import oldest_first, validate_requests

END = '<!-- /sdlc-itsm -->'


def synchronize(client, config, request):
    identity = json.dumps([config['source'], request['request_id']], ensure_ascii=False)
    digest = hashlib.sha256(identity.encode()).hexdigest()
    marker = f'<!-- sdlc-itsm:{digest} -->'
    label = f'sdlc-itsm-{digest}'
    path = f"projects/{config['project_id']}/issues"
    # Code indentation keeps source content inert in the issue description.
    source = '\n'.join('    ' + line for line in (
        f"ITSM 요청: {request['request_id']}\n버전: {request['revision']}\n"
        f"제목: {request['title']}\n\n{request['summary']}").splitlines())
    block = f'{marker}\n\n{source}\n\n{END}'
    response = client.get(path, params={'labels': label, 'scope': 'all', 'per_page': 2})
    response.raise_for_status()
    issues = response.json()
    if len(issues) > 1:
        raise ValueError('Multiple GitLab issues share the ITSM key')
    if issues:
        issue, = issues
        description = issue['description'] or ''
        before, found, region = description.partition(marker)
        _, closed, after = region.partition('\n\n' + END)
        if not found or not closed:
            raise ValueError('GitLab issue is missing its managed ITSM block')
        updated = before + block + after
        status = 'existing'
        if updated != description:
            client.put(f"{path}/{issue['iid']}", json={'description': updated}).raise_for_status()
            status = 'updated'
    else:
        response = client.post(path, json={
            'title': request['title'], 'description': block, 'labels': label,
        })
        response.raise_for_status()
        issue = response.json()
        status = 'created'
    return {'iid': issue['iid'], 'url': issue['web_url'], 'status': status, **request}


def destination(config, routes, request):
    if routes is None:
        return config
    system = request.get('target_system')
    matches = [row for row in routes if isinstance(system, str) and system.strip()
               and row['target_system'] == system
               and (not row.get('component') or row['component'] == request.get('component'))]
    if len(matches) != 1:
        raise ValueError('Expected exactly one operational mapping for this ITSM row')
    route, = matches
    selected = {**config, 'gitlab_url': route['gitlab_url'], 'project_id': route['project_id']}
    for field in ('token_env', 'token_ref', 'token_file'):
        selected.pop(field, None)
        if field in route:
            selected[field] = route[field]
    if 'dispatch' in config:
        selected['dispatch'] = {**config['dispatch'], 'repository': route.get('repository', '')}
    return selected


def open_client(config):
    base = urlsplit(config['gitlab_url'])
    if (base.scheme != 'https' or not base.hostname or base.username or base.password
            or base.query or base.fragment or type(config['project_id']) is not int
            or config['project_id'] < 1):
        raise ValueError('Expected HTTPS GitLab URL and numeric project ID')
    if config.get('token_file'):
        import stat
        with Path(config['token_file']).open(encoding='utf-8') as secret:
            mode = os.fstat(secret.fileno()).st_mode
            if not stat.S_ISREG(mode) or mode & 0o077:
                raise ValueError('GitLab token file must be a private regular file')
            token = secret.read().strip()
    else:
        token = resolve(config, 'token')
    if not token:
        raise ValueError('Missing GitLab token')
    return httpx.Client(base_url=config['gitlab_url'].rstrip('/') + '/api/v4/',
                        headers={'PRIVATE-TOKEN': token}, timeout=20, follow_redirects=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument("--dispatch", action="store_true", help="Run eligible ticket stages after intake")
    parser.add_argument("--complete", metavar="ASSIGNMENT", help="Record one verified native stage result")
    parser.add_argument("--intake", required=True, type=Path, help="Validated handoff from the requirements agent")
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding='utf-8'))
        routes = None
        if 'routing_file' in config or 'project_id' not in config:
            default_routes = Path(__file__).resolve().parents[3] / 'wiki/itsm-gitlab-routes.json'
            registry = args.config.parent / config.get('routing_file', default_routes)
            routes = json.loads(registry.read_text(encoding='utf-8'))
            if not isinstance(routes, list) or not all(isinstance(row, dict) and
                    {'target_system', 'project_id', 'gitlab_url'} <= row.keys() for row in routes):
                raise ValueError('Invalid routing registry')
        if type(config['batch_size']) is not int or not 1 <= config['batch_size'] <= 100:
            raise ValueError('Invalid batch size')
        requests = validate_requests(json.loads(args.intake.read_text(encoding="utf-8")), config["batch_size"])
        if config.get("oldest_first") or any("created_at" in row for row in requests):
            requests = oldest_first(requests)
        failures = 0
        with scheduler_lock(), ExitStack() as stack:
            clients = {}
            for index, request in enumerate(requests, start=1):
                try:
                    selected = destination(config, routes, request)
                    if (args.dispatch or args.complete) and not selected.get('dispatch', {}).get('repository'):
                        raise ValueError('Missing dispatch repository')
                    key = tuple(selected.get(k) for k in ('gitlab_url', 'token_ref', 'token_env', 'token_file'))
                    if key not in clients:
                        clients[key] = stack.enter_context(open_client(selected))
                    client = clients[key]
                    if type(selected['project_id']) is not int or selected['project_id'] < 1:
                        raise ValueError('Invalid project ID')
                    identity = json.dumps([config['source'], request['request_id']], ensure_ascii=False)
                    label = 'sdlc-itsm-' + hashlib.sha256(identity.encode()).hexdigest()
                    checked = {(selected['gitlab_url'], selected['project_id'])}
                    for route in routes or ():
                        target = (route['gitlab_url'], route['project_id'])
                        if target in checked:
                            continue
                        checked.add(target)
                        other = route
                        remote_key = tuple(other.get(k) for k in ('gitlab_url', 'token_ref', 'token_env', 'token_file'))
                        if remote_key not in clients:
                            clients[remote_key] = stack.enter_context(open_client(other))
                        response = clients[remote_key].get(f'projects/{target[1]}/issues',
                            params={'labels': label, 'scope': 'all', 'per_page': 1})
                        response.raise_for_status()
                        if response.json():
                            raise ValueError('Existing ITSM issue belongs to another project')
                    ticket = synchronize(client, selected, request)
                    ticket.update(project_id=selected['project_id'], gitlab_url=selected['gitlab_url'])
                    print(json.dumps(ticket, ensure_ascii=False))
                    if args.dispatch or args.complete:
                        from ticket_dispatch import dispatch_batch
                        for result in dispatch_batch(client, selected, [ticket], args.complete):
                            failures += int("error" in result)
                            print(json.dumps({**result, 'url': ticket['url']}))
                except httpx.HTTPStatusError as error:
                    failures += 1
                    print(f'Row {index}: GitLab HTTP {error.response.status_code}', file=sys.stderr)
                except (ValueError, OSError, httpx.RequestError) as error:
                    failures += 1
                    message = str(error) if type(error) is ValueError else type(error).__name__
                    print(f'Row {index}: {message}', file=sys.stderr)
        return int(bool(failures))
    except Exception as error:
        print(f'ITSM batch failed: {type(error).__name__}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
