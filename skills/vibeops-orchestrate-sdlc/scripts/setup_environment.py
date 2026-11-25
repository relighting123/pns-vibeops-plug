"""Interactively register a GitLab project for an ITSM system."""
import argparse
import importlib.util
from getpass import getpass, GetPassWarning
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote, unquote, urlsplit
import warnings

import httpx


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True,
                                   timeout=10, stderr=subprocess.DEVNULL).strip()


def discover(repo):
    origin = git(repo, 'remote', 'get-url', 'origin')
    if '://' not in origin and '@' in origin and ':' in origin:
        host, path = origin.split('@', 1)[1].split(':', 1)
        origin = 'ssh://' + host + '/' + path
    remote = urlsplit(origin)
    if remote.scheme not in ('https', 'http', 'ssh') or not remote.hostname:
        raise ValueError('Expected an HTTP(S) or SSH origin')
    host = remote.hostname
    if ':' in host:
        host = '[' + host + ']'
    if remote.scheme != 'ssh' and remote.port:
        host += ':' + str(remote.port)
    return 'https://' + host, unquote(remote.path.strip('/')).removesuffix('.git')


def ask(label, default=None):
    value = input(f'{label} [{default}] ' if default else f'{label}: ').strip()
    if not (value or default):
        raise ValueError(f'{label} is required')
    return value or default


def confirm(label):
    if input(label + ' [y/N] ').strip().lower() not in ('y', 'yes'):
        raise ValueError('Cancelled')


def save(path, obj, *, secret=False):
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     delete=False) as out:
        temporary = Path(out.name)
        try:
            out.write(obj if secret else json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
            out.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def setup(path):
    config = json.loads(path.read_text()) if path.exists() else {}
    repo = Path(ask('로컬 Git 경로', str(Path.cwd()))).expanduser().resolve()
    repo = Path(git(repo, 'rev-parse', '--show-toplevel'))
    try:
        server, project_path = discover(repo)
    except (ValueError, subprocess.CalledProcessError):
        server, project_path = None, None
    server = ask('GitLab HTTPS 주소', server).rstrip('/')
    base = urlsplit(server)
    if (base.scheme != 'https' or not base.hostname or base.username or base.password
            or base.query or base.fragment):
        raise ValueError('Expected a GitLab HTTPS URL without credentials')
    project_path = ask('GitLab 그룹/저장소 경로', project_path)
    system = ask('ITSM 대상 시스템 코드')
    component = input('ITSM 구성요소 코드 [생략 가능] ').strip()
    confirm(f'{server}/{project_path}에 토큰을 보내 프로젝트를 확인할까요?')
    with warnings.catch_warnings():
        warnings.simplefilter('error', GetPassWarning)
        token = getpass('GitLab 토큰 입력 (화면에 표시되지 않음): ').strip()
    if not token:
        raise ValueError('GitLab token is required')
    with httpx.Client(base_url=server + '/api/v4/', headers={'PRIVATE-TOKEN': token},
                      follow_redirects=False, timeout=15) as client:
        response = client.get('projects/' + quote(project_path, safe=''))
        response.raise_for_status()
        project = response.json()
        if project['path_with_namespace'] != project_path:
            raise ValueError('GitLab project path differs from the selected path')
        client.get(f"projects/{project['id']}/issues", params={'per_page': 1}).raise_for_status()
    print(f"확인된 프로젝트 {project_path} (ID {project['id']})")
    for key, label in (
        ('source', 'ITSM 소스 이름'), ('oracle_config', 'Oracle 프로필 JSON 경로'),
        ('database', 'Oracle 프로필 ID'), ('query', '등록된 ITSM SELECT 이름'),
    ):
        config[key] = ask(label, config.get(key))
    oracle_config = Path(config['oracle_config']).expanduser().resolve()
    if not oracle_config.is_file():
        raise ValueError('Oracle profile file does not exist')
    config['oracle_config'] = str(oracle_config)
    config.setdefault('batch_size', 20)
    config.setdefault('state_db', str(path.parent / 'itsm.sqlite3'))
    config['oldest_first'] = True
    registry = path.parent / config.get('routing_file', 'itsm-gitlab-routes.json')
    config['routing_file'] = str(registry)
    routes = json.loads(registry.read_text()) if registry.exists() else []
    import hashlib
    identity = json.dumps([server, project['id'], system, component])
    secrets = Path.home() / '.config/pns-vibeops/tokens'
    secret = secrets / hashlib.sha256(identity.encode()).hexdigest()
    route = dict(target_system=system, gitlab_url=server, project_id=project['id'],
                 repository=str(repo), token_file=str(secret))
    if component:
        route['component'] = component
    routes = [row for row in routes if (row['target_system'], row.get('component', ''))
              != (system, component)]
    if any(row['target_system'] == system and (not component or not row.get('component')) for row in routes):
        raise ValueError('System-wide and component-specific routes overlap')
    confirm(f'{system} → {project_path} 등록과 토큰의 로컬 저장을 진행할까요?')
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    secrets.mkdir(mode=0o700, parents=True, exist_ok=True)
    save(secret, token, secret=True)
    save(registry, [*routes, route])
    save(path, config)
    print(f'설정 파일 {path}')
    print('GitLab 프로젝트와 이슈 읽기 확인 완료. Oracle 조회와 이슈 발행은 실행 점검에서 확인하세요.')


def check(path):
    from gitlab_issue_sync import open_client
    from oracle_client.common import QueryError
    from oracle_client.connections import load_profile

    config = json.loads(path.read_text())
    failures = []

    def report(label, action):
        try:
            action()
            print(f'OK {label}')
        except (ValueError, KeyError, OSError, QueryError, RuntimeError, httpx.HTTPError, subprocess.SubprocessError) as exc:
            failures.append(label)
            detail = f' HTTP {exc.response.status_code}' if isinstance(exc, httpx.HTTPStatusError) else ''
            print(f'CHECK {label} ({type(exc).__name__}{detail})')

    def oracle():
        if importlib.util.find_spec('oracledb') is None:
            raise ValueError('Missing oracledb')
        load_profile(config['oracle_config'], config['database'])

    report('Oracle driver and profile', oracle)
    def state_directory():
        state = Path(config['state_db']).expanduser()
        if not state.is_absolute() or not state.parent.is_dir() or not os.access(state.parent, os.W_OK):
            raise ValueError('Expected an absolute state_db path in a writable directory')

    report('SQLite directory', state_directory)
    registry = path.parent / config.get('routing_file', Path(__file__).resolve().parents[3]
                                       / 'wiki/itsm-gitlab-routes.json')
    routes = [config] if 'routing_file' not in config and 'project_id' in config else json.loads(registry.read_text())
    if not routes:
        print('CHECK No routes registered')
        failures.append('routes')
    dispatch = config.get('dispatch')
    for route in routes:
        def project():
            with open_client(route) as client:
                project_id = route['project_id']
                data = client.get(f'projects/{project_id}')
                data.raise_for_status()
                client.get(f'projects/{project_id}/issues', params={'per_page': 1}).raise_for_status()
                repository = route.get('repository') or (dispatch or {}).get('repository')
                if repository and discover(repository) != (route['gitlab_url'].rstrip('/'),
                                                          data.json()['path_with_namespace']):
                    raise ValueError('Repository differs from GitLab project')

        report(f"GitLab route {route.get('target_system', 'single project')}", project)
        if dispatch:
            def worktree():
                repo = route.get('repository') or dispatch['repository']
                git(repo, 'rev-parse', '--verify', dispatch['base_ref'] + '^{commit}')
                if not Path(dispatch['worktrees']).is_absolute() or not 1 <= dispatch.get('workers', 3) <= 16:
                    raise ValueError('Invalid worker or worktree settings')
                from ticket_dispatch import STAGES
                stages = STAGES if dispatch.get('deployment') else STAGES[:-1]
                if not all(dispatch['approvers'].get(stage) for stage in stages):
                    raise ValueError('Missing stage approver')
                command = dispatch['verify_command']
                if not isinstance(command, list) or not command:
                    raise ValueError('Missing verify command')

            report('Dispatch base ref, worktree, worker limit, approvers and test command', worktree)
    if not dispatch:
        print('INFO Dispatch configuration is required to assign workers')
    print('INFO Live Oracle query, GitLab issue write, host agents and shared wiki need an end-to-end smoke test')
    return int(bool(failures))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path,
                        default=Path.home() / '.config/pns-vibeops/batch.json')
    parser.add_argument("--check", action="store_true", help="Read-only configuration and GitLab checks")
    args = parser.parse_args()
    if not args.check and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        parser.error('Run in your local interactive terminal so token input remains hidden')
    try:
        path = args.config.expanduser().resolve()
        if args.check:
            return check(path)
        setup(path)
    except httpx.HTTPStatusError as exc:
        parser.error(f'GitLab HTTP {exc.response.status_code}')
    except (httpx.RequestError, OSError, subprocess.SubprocessError, GetPassWarning) as exc:
        parser.error(type(exc).__name__)
    except (ValueError, EOFError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    raise SystemExit(main())
