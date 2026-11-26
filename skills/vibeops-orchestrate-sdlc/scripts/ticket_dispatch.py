"""Run one approved stage per ticket on a local scheduler tick."""
from issue_state import ACTIVE, load, notes, save
import hashlib
import json
from pathlib import Path
import re
import subprocess
import uuid
from urllib.parse import quote

STAGES = ('analyze-requirements', 'design-system', 'implement-feature',
          'verify-change', 'review-release', 'deploy-release')

REPORT_NAMES = dict(zip(STAGES, ('requirements.md', 'design.md', 'implementation.md',
                                 'test-results.md', 'review.md', 'release.md')))


def git(folder, *args):
    return subprocess.check_output(['git', *args], cwd=folder, text=True).strip()


REVIEW_WAITING = '검토 대기'
REVIEW_DONE = '검토 완료'
STATUS_FIELDS = 'id widgets { ... on WorkItemWidgetStatus { status { name category } } }'


def graphql(client, query, **variables):
    endpoint = str(client.base_url).removesuffix('/api/v4/') + '/api/graphql'
    payload = gitlab_json(client, 'post', endpoint, json={'query': query, 'variables': variables})
    if payload.get('errors') or not payload.get('data'):
        raise ValueError('GitLab Work Item Status GraphQL request failed')
    return payload['data']


def work_item_status(item):
    status = next((widget['status'] for widget in (item or {}).get('widgets', [])
                   if widget.get('status')), None)
    if status is None:
        raise ValueError('GitLab Work Item Status is unavailable')
    return status


def issue_approved(client, row, path, gate, stage, revision, allowed):
    project_path, iid = path.rsplit('/issues/', 1)
    project = gitlab_json(client, 'get', project_path)
    data = graphql(client, f"""
        query ReviewStatus($project: ID!, $iid: String!) {{
          namespace(fullPath: $project) {{ workItem(iid: $iid) {{ {STATUS_FIELDS} }} }}
        }}
        """, project=project['path_with_namespace'], iid=iid)
    item = (data.get('namespace') or {}).get('workItem')
    status = work_item_status(item)

    notice = row.get('notice') or {}
    target = [path, gate, stage, revision]
    if notice.get('target') != target or 'status_note_id' not in notice:
        data = graphql(client, f"""
            mutation WaitForReview($id: WorkItemID!, $name: String!) {{
              workItemUpdate(input: {{id: $id, statusWidget: {{name: $name}}}}) {{
                errors workItem {{ {STATUS_FIELDS} }}
              }}
            }}
            """, id=item['id'], name=REVIEW_WAITING)
        result = data['workItemUpdate']
        if result['errors'] or work_item_status(result['workItem']) != {
                'name': REVIEW_WAITING, 'category': 'IN_PROGRESS'}:
            raise ValueError('Configure 검토 대기 as an In progress status')
        artifact = row.get('artifact')
        evidence = f"\n\n검토 자료: {artifact['link']}" if artifact else ''
        posted = gitlab_json(client, 'post', path + '/notes', json={
            'body': f'{stage} · {revision} 검토 대기. 완료하면 이슈의 Status를 {REVIEW_DONE}(으)로 바꾸세요.{evidence}'
        })
        row['notice'] = {'target': target, 'status_note_id': posted['id']}
        return False

    if status != {'name': REVIEW_DONE, 'category': 'IN_PROGRESS'}:
        return False
    for note in notes(client, path):
        if note['id'] <= notice['status_note_id']:
            break
        if note.get('system') and note['body'].startswith('set status to '):
            name = note['body'].removeprefix('set status to ').strip()
            return name in (REVIEW_DONE, f'**{REVIEW_DONE}**', f'`{REVIEW_DONE}`') and note['author']['id'] in allowed
    return False


def gitlab_json(client, method, path, **kwargs):
    response = getattr(client, method)(path, **kwargs)
    response.raise_for_status()
    return response.json()


def project_remote(client, project):
    # Construct the push URL on the same server as the issue API.
    namespace = project['path_with_namespace']
    if not re.fullmatch(r'[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)+', namespace):
        raise ValueError('Invalid GitLab project path')
    return str(client.base_url).removesuffix('/api/v4/') + '/' + namespace + '.git'


def merge_request(client, row, project_path, issue_path, key, revision, branch, folder,
                  head, target_override, create=False):
    endpoint = project_path + '/merge_requests'
    if row['mr']:
        return gitlab_json(client, 'get', f"{endpoint}/{row['mr']}"), False
    if not create:
        return None, False

    project = gitlab_json(client, 'get', project_path)
    target = target_override or project['default_branch']
    git(folder, 'check-ref-format', 'refs/heads/' + target)
    marker = '<!-- vibeops:' + hashlib.sha256(json.dumps([key, revision]).encode()).hexdigest() + ' -->'
    candidates = gitlab_json(client, 'get', endpoint, params={
        'source_branch': branch, 'target_branch': target, 'state': 'opened',
    })
    matches = [mr for mr in candidates if marker in (mr.get('description') or '')
               and mr.get('source_project_id') == project['id']]
    if len(matches) > 1:
        raise ValueError('Multiple merge requests match the ticket revision')
    if candidates and not matches:
        raise ValueError('Close or reconcile the previous merge request before publishing this revision')
    git(folder, 'push', '--', project_remote(client, project), f'{head}:refs/heads/{branch}')
    if matches:
        mr, = matches
    else:
        iid = issue_path.rsplit('/', 1)[-1]
        issue_title = gitlab_json(client, 'get', issue_path)['title']
        mr = gitlab_json(client, 'post', endpoint, json={
            'source_branch': branch, 'target_branch': target,
            'title': f'Draft: #{iid} {issue_title}'[:255],
            'description': f'ITSM 이슈 #{iid} · 승인된 설계 커밋 `{head}`\n\n{marker}',
        })
    row['mr'] = mr['iid']
    return mr, True


def verify_checkout(opts, folder, sha):
    command = opts.get('verify_command')
    if not isinstance(command, list) or not command or not all(isinstance(v, str) and v for v in command):
        return False
    result = subprocess.run(command, cwd=folder, timeout=600)
    return (result.returncode == 0 and git(folder, 'rev-parse', 'HEAD') == sha
            and not git(folder, 'status', '--porcelain'))


def publish_report(client, project_path, report, folder, branch, sha, release_stage):
    if release_stage:
        response = gitlab_json(client, 'post', project_path + '/uploads',
                               files={'file': (report.name, report.read_bytes(), 'text/markdown')})
        url = response['url']
        if not re.fullmatch(r'/uploads/[a-zA-Z0-9]+/[a-zA-Z0-9.-]+', url):
            raise ValueError('Unexpected GitLab report upload URL')
        return f'[{report.name}]({url})'

    project = gitlab_json(client, 'get', project_path)
    git(folder, 'push', '--', project_remote(client, project), f'{sha}:refs/heads/{branch}')
    path = quote(report.relative_to(folder).as_posix())
    return f"[{report.name}]({project['web_url']}/-/blob/{sha}/{path})"


def dispatch(client, config, ticket, completion=None):
    opts = config['dispatch']
    iid = ticket['iid']
    scope = [str(client.base_url), config['project_id'], iid]
    key = hashlib.sha256(json.dumps(scope).encode()).hexdigest()
    folder = Path(opts['worktrees']).resolve() / key
    repo = Path(opts['repository']).resolve()
    stages = STAGES if opts.get('deployment') else STAGES[:-1]
    path = f"projects/{config['project_id']}/issues/{iid}"
    bot = gitlab_json(client, 'get', 'user')['id']
    row = load(client, path, bot, ticket['revision'])
    previous = row.copy()

    def advance():
        if row['running'] and completion != row['gate']:
            return 'assigned; inspect existing ticket checkpoint'
        if completion is not None and (not row['running'] or completion != row['gate']):
            return 'stale completion'
        if row['revision'] != ticket['revision']:
            row.update(revision=ticket['revision'], stage=0, session=None, gate=uuid.uuid4().hex,
                       head=None, running=False, verified=None, notice=None, mr=None, artifact=None)
            return 'input changed; new approval required'
        index = row['stage']
        if index == len(stages):
            return 'completed'
        issue = client.get(path)
        issue.raise_for_status()
        if issue.json()['state'] != 'opened':
            return 'closed'
        stage = stages[index]
        branch = 'sdlc/' + key
        project_path = f"projects/{config['project_id']}"
        if index < stages.index('implement-feature') and completion is None and not issue_approved(
                client, row, path, row['gate'], stage, row['head'] or ticket['revision'],
                opts['approvers'][stage]):
            return 'waiting for ' + stage
        if not folder.exists():
            folder.parent.mkdir(parents=True, exist_ok=True)
            git(repo, 'worktree', 'add', '-b', branch, str(folder), opts['base_ref'])
        if git(folder, 'branch', '--show-current') != branch or git(folder, 'status', '--porcelain'):
            return 'inspect ticket worktree'
        head = git(folder, 'rev-parse', 'HEAD')
        release_stage = stage in ('verify-change', 'review-release', 'deploy-release')
        if release_stage:
            if head != row['head'] or (stage != 'verify-change' and row['verified'] != head):
                row.update(verified=None, stage=stages.index('verify-change'), gate=uuid.uuid4().hex,
                           head=head, running=False, notice=None, artifact=None)
                return 'verification and fresh approval required'
        mr = None
        approval_path = path
        if stage == 'implement-feature' and completion is None:
            if not issue_approved(client, row, path, row['gate'], 'design-signoff',
                                  row['head'], opts['approvers']['design-system']):
                return 'waiting for design signoff'
            if head != row['head']:
                return 'inspect changed checkpoint'
            active = len(gitlab_json(client, 'get', project_path + '/issues', params={'labels': ACTIVE, 'scope': 'all', 'per_page': 16}))
            if active >= opts.get('workers', 3):
                return 'deferred: active ticket limit'
        if index >= stages.index('implement-feature'):
            mr, created = merge_request(
                client, row, project_path, path, key, ticket['revision'], branch, folder,
                row['head'], opts.get('target_branch'), create=stage in ('implement-feature', 'verify-change', 'review-release'),
            )
            if mr is None:
                return 'waiting for linked merge request'
            approval_path = f"{project_path}/merge_requests/{mr['iid']}"
            if created:
                gitlab_json(client, 'post', path + '/notes', json={
                    'body': f"설계 승인 · 구현 Draft MR !{mr['iid']} · {mr['web_url']}",
                })
            expected_state = 'merged' if stage == 'deploy-release' else 'opened'
            if mr['state'] != expected_state:
                return 'waiting for merge' if expected_state == 'merged' else 'inspect merge request state'
        if completion is None and stage in ('verify-change', 'review-release') and not issue_approved(
                client, row, path, row['gate'], stage, row['head'] or ticket['revision'],
                opts['approvers'][stage]):
            return 'waiting for ' + stage
        assignment_folder = folder
        assignment_sha = head
        if stage in ('verify-change', 'review-release', 'deploy-release') and mr['sha'] != head:
            return 'waiting for merge request source revision'
        if stage == 'deploy-release':
            merged_sha = mr.get('merge_commit_sha') or mr.get('squash_commit_sha') or mr['sha']
            if not re.fullmatch(r'[0-9a-f]{40}', merged_sha):
                return 'waiting for merged commit'
            if completion is None and not issue_approved(
                    client, row, path, row['gate'], stage, merged_sha,
                    opts['approvers'][stage]):
                return 'waiting for ' + stage
            project = gitlab_json(client, 'get', project_path)
            target = mr['target_branch']
            if target != (opts.get('target_branch') or project['default_branch']):
                return 'inspect merge request target branch'
            git(folder, 'check-ref-format', 'refs/heads/' + target)
            git(folder, 'fetch', '--', project_remote(client, project), f'refs/heads/{target}')
            git(folder, 'merge-base', '--is-ancestor', merged_sha, 'FETCH_HEAD')
            assignment_folder = folder.with_name(folder.name + '-deploy-' + merged_sha)
            if not assignment_folder.exists():
                git(folder, 'worktree', 'add', '--detach', str(assignment_folder), merged_sha)
            assignment_sha = merged_sha
            if (git(assignment_folder, 'rev-parse', 'HEAD') != merged_sha
                    or git(assignment_folder, 'status', '--porcelain')):
                return 'inspect deployment worktree'
            if completion is not None and row['session'] != merged_sha:
                return 'deployment assignment revision changed'
            if completion is None and not verify_checkout(opts, assignment_folder, merged_sha):
                return 'merged commit verification failed'
        if release_stage:
            report = folder.parent / '.reports' / key / row['gate'] / REPORT_NAMES[stage]
        else:
            report = folder / 'artifacts' / 'vibeops' / REPORT_NAMES[stage]
        if completion is not None:
            if not report.is_file() or report.is_symlink() or not report.read_text(encoding='utf-8').strip():
                return 'stage report required: ' + report.name
            if stage == 'verify-change':
                if not verify_checkout(opts, folder, head):
                    return 'verification failed or checkout changed'
                row['verified'] = head
            elif not release_stage:
                if head == row['session']:
                    return 'new stage commit required'
                git(folder, 'merge-base', '--is-ancestor', row['session'], head)
                git(folder, 'ls-files', '--error-unmatch', 'artifacts/sdlc-progress.md')
                report_path = report.relative_to(folder).as_posix()
                git(folder, 'ls-files', '--error-unmatch', report_path)
                if not git(folder, 'diff', '--name-only', row['session'], head, '--', report_path):
                    return 'updated stage report required: ' + report.name
            report_sha = assignment_sha if release_stage else head
            link = publish_report(client, project_path, report, folder, branch, report_sha, release_stage)
            if stage == 'review-release':
                title = re.sub(r'^(?:Draft:|WIP:)\s*', '', mr['title'], flags=re.IGNORECASE)
                if title != mr['title']:
                    gitlab_json(client, 'put', approval_path, json={'title': title})
            notice = f'SDLC {stage} 완료 · `{report_sha}`\n\n{link}'
            if mr:
                gitlab_json(client, 'post', approval_path + '/notes', json={'body': notice})
                notice += f" · !{mr['iid']}"
            client.post(path + '/notes', json={'body': notice}).raise_for_status()
            row.update(stage=index + 1, gate=uuid.uuid4().hex, head=head, running=False, notice=None,
                       artifact={'link': link, 'sha': report_sha})
            return stage + ' completed'
        if row['head'] and head != row['head']:
            return 'inspect changed checkpoint'
        active = len(gitlab_json(client, 'get', project_path + '/issues', params={'labels': ACTIVE, 'scope': 'all', 'per_page': 16}))
        if active >= opts.get('workers', 3):
            return 'deferred: active ticket limit'
        report.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        row.update(running=True, session=assignment_sha)
        role = ('requirements', 'design', 'develop', 'test', 'review', 'deploy')[index]
        return {'stage': stage, 'target_sha': assignment_sha, 'agent': 'vibeops-' + role, 'worktree': str(assignment_folder), 'assignment': row['gate'], 'report_path': str(report)}

    result = advance()
    if row != previous:
        if row['running'] and not previous['running']:
            client.put(path, json={'add_labels': ACTIVE}).raise_for_status()
        row['stage_name'] = stages[row['stage']] if row['stage'] < len(stages) else 'done'
        save(client, path, row)
    if not row['running']:
        issue = gitlab_json(client, 'get', path)
        if ACTIVE in issue.get('labels', []):
            client.put(path, json={'remove_labels': ACTIVE}).raise_for_status()
    return result


def dispatch_batch(client, config, tickets, completion=None):
    workers = config['dispatch'].get('workers', 3)
    if type(workers) is not int or not 1 <= workers <= 16:
        raise ValueError('workers must be between 1 and 16')

    results = []
    for ticket in tickets:
        try:
            results.append({'iid': ticket['iid'], 'dispatch': dispatch(client, config, ticket, completion)})
        except Exception as exc:
            results.append({'iid': ticket['iid'], 'error': type(exc).__name__})
    return results
