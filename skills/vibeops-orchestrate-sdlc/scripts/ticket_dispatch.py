"""Run one approved stage per ticket on a local scheduler tick."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import uuid

STAGES = ('analyze-requirements', 'design-system', 'implement-feature',
          'verify-change', 'review-release', 'deploy-release')


def git(folder, *args):
    return subprocess.check_output(['git', *args], cwd=folder, text=True).strip()


# Match complete approval phrases so a negation or condition cannot pass by substring.
APPROVAL = re.compile(
    r'(?:(?:검토 결과|검토 결과는)\s*[:：]?\s*)?'
    r'(?:승인(?:합니다|했습니다|할게요)?|이상\s*(?:없음|없습니다|없어요)|'
    r'문제\s*(?:없음|없습니다|없어요)|'
    r'(?:다음 단계로\s*)?진행(?:해도 됩니다|해 주세요|해주세요))'
    r'[.!。]*', re.IGNORECASE,
)


def issue_approved(client, db, path, gate, stage, revision, allowed):
    endpoint = path + '/notes'
    response = client.get(endpoint, params={'per_page': 100, 'sort': 'desc'})
    response.raise_for_status()
    notes = response.json()
    command = f'approve {stage} {gate} {revision}'
    request_key = hashlib.sha256(command.encode()).hexdigest()
    request = db.execute('SELECT note_id FROM ticket_approval_request WHERE gate=?',
                         (request_key,)).fetchone()
    if request is None:
        # Preserve an explicit approval for this stage and revision during rollout.
        if any(not note.get('system') and note['author']['id'] in allowed
               and note['body'] == command for note in notes):
            return True
        notice = (f'SDLC 승인 요청 · {stage} · {revision}\n\n'
                  '검토를 마쳤다면 이 요청 이후에 “승인합니다” 또는 “이상 없음”으로 댓글을 남겨 주세요. '
                  '조건이나 수정 요청이 있으면 함께 적어 주세요.')
        response = client.post(endpoint, json={'body': notice})
        response.raise_for_status()
        db.execute('INSERT INTO ticket_approval_request VALUES (?, ?)',
                   (request_key, response.json()['id']))
        return False

    current = request['note_id']
    candidates = [note for note in notes if note['id'] > current
                  and not note.get('system') and note['author']['id'] in allowed]
    if not candidates:
        return False
    body = max(candidates, key=lambda note: note['id'])['body']
    normalized = ' '.join(body.split())
    return body == command or APPROVAL.fullmatch(normalized) is not None


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


def merge_request(client, db, project_path, issue_path, key, revision, branch, folder,
                  head, target_override, create=False):
    endpoint = project_path + '/merge_requests'
    record = db.execute('SELECT iid FROM ticket_merge_request WHERE id=? AND revision=?',
                        (key, revision)).fetchone()
    if record:
        return gitlab_json(client, 'get', f"{endpoint}/{record['iid']}"), False
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
    db.execute('INSERT OR REPLACE INTO ticket_merge_request VALUES (?, ?, ?)',
               (key, revision, mr['iid']))
    return mr, True


def verify_checkout(opts, folder, sha):
    command = opts.get('verify_command')
    if not isinstance(command, list) or not command or not all(isinstance(v, str) and v for v in command):
        return False
    result = subprocess.run(command, cwd=folder, timeout=600)
    return (result.returncode == 0 and git(folder, 'rev-parse', 'HEAD') == sha
            and not git(folder, 'status', '--porcelain'))


def dispatch(client, config, ticket, completion=None):
    opts = config['dispatch']
    iid = ticket['iid']
    scope = [str(client.base_url), config['project_id'], iid]
    key = hashlib.sha256(json.dumps(scope).encode()).hexdigest()
    folder = Path(opts['worktrees']).resolve() / key
    repo = Path(opts['repository']).resolve()
    stages = STAGES if opts.get('deployment') else STAGES[:-1]
    path = f"projects/{config['project_id']}/issues/{iid}"
    with closing(sqlite3.connect(Path(config['state_db']).expanduser(), timeout=30)) as db:
        db.row_factory = sqlite3.Row
        with db:
            db.execute('CREATE TABLE IF NOT EXISTS ticket_run (id TEXT PRIMARY KEY, revision TEXT, '
                       'stage INTEGER, session TEXT, gate TEXT, head TEXT, running INTEGER)')
            db.execute('CREATE TABLE IF NOT EXISTS ticket_verification (id TEXT PRIMARY KEY, sha TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS ticket_approval_request ('
                       'gate TEXT PRIMARY KEY, note_id INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS ticket_merge_request ('
                       'id TEXT PRIMARY KEY, revision TEXT NOT NULL, iid INTEGER NOT NULL)')
            db.execute('INSERT OR IGNORE INTO ticket_run VALUES (?, ?, 0, NULL, ?, NULL, 0)',
                       (key, ticket['revision'], uuid.uuid4().hex))
        db.execute('BEGIN IMMEDIATE')
        try:
            row = db.execute('SELECT * FROM ticket_run WHERE id=?', (key,)).fetchone()
            if row['running'] and completion != row['gate']:
                return 'assigned; inspect existing ticket checkpoint'
            if completion is not None and (not row['running'] or completion != row['gate']):
                return 'stale completion'
            if row['revision'] != ticket['revision']:
                with db:
                    db.execute('DELETE FROM ticket_verification WHERE id=?', (key,))
                    db.execute('UPDATE ticket_run SET revision=?, stage=0, session=NULL, gate=?, head=NULL, running=0 WHERE id=?',
                               (ticket['revision'], uuid.uuid4().hex, key))
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
                    client, db, path, row['gate'], stage, row['head'] or ticket['revision'],
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
                verified = db.execute('SELECT sha FROM ticket_verification WHERE id=?', (key,)).fetchone()
                if (head != row['head'] or
                        (stage != 'verify-change' and (not verified or verified['sha'] != head))):
                    db.execute('DELETE FROM ticket_verification WHERE id=?', (key,))
                    db.execute('UPDATE ticket_run SET stage=?, gate=?, head=?, running=0 WHERE id=?',
                               (stages.index('verify-change'), uuid.uuid4().hex, head, key))
                    return 'verification and fresh approval required'
            mr = None
            approval_path = path
            if stage == 'implement-feature' and completion is None:
                if not issue_approved(client, db, path, row['gate'], 'design-signoff',
                                      row['head'], opts['approvers']['design-system']):
                    return 'waiting for design signoff'
                if head != row['head']:
                    return 'inspect changed checkpoint'
                active, = db.execute('SELECT count(*) FROM ticket_run WHERE running=1').fetchone()
                if active >= opts.get('workers', 3):
                    return 'deferred: active ticket limit'
            if index >= stages.index('implement-feature'):
                mr, created = merge_request(
                    client, db, project_path, path, key, ticket['revision'], branch, folder,
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
                    client, db, approval_path, row['gate'], stage, row['head'] or ticket['revision'],
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
                        client, db, approval_path, row['gate'], stage, merged_sha,
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
            if completion is not None:
                if stage == 'verify-change':
                    if not verify_checkout(opts, folder, head):
                        return 'verification failed or checkout changed'
                    db.execute('INSERT OR REPLACE INTO ticket_verification VALUES (?, ?)', (key, head))
                elif not release_stage:
                    if head == row['session']:
                        return 'new stage commit required'
                    git(folder, 'merge-base', '--is-ancestor', row['session'], head)
                    git(folder, 'ls-files', '--error-unmatch', 'artifacts/sdlc-progress.md')
                if stage == 'implement-feature':
                    project = gitlab_json(client, 'get', project_path)
                    git(folder, 'push', '--', project_remote(client, project), f'{head}:refs/heads/{branch}')
                if stage == 'review-release':
                    title = re.sub(r'^(?:Draft:|WIP:)\s*', '', mr['title'], flags=re.IGNORECASE)
                    if title != mr['title']:
                        gitlab_json(client, 'put', approval_path, json={'title': title})
                notice = f'SDLC {stage} 완료 · {assignment_sha}'
                if mr:
                    gitlab_json(client, 'post', approval_path + '/notes', json={'body': notice})
                    notice += f" · !{mr['iid']}"
                client.post(path + '/notes', json={'body': notice}).raise_for_status()
                db.execute('UPDATE ticket_run SET stage=?, gate=?, head=?, running=0 WHERE id=?',
                           (index + 1, uuid.uuid4().hex, head, key))
                return stage + ' completed'
            if row['head'] and head != row['head']:
                return 'inspect changed checkpoint'
            active, = db.execute('SELECT count(*) FROM ticket_run WHERE running=1').fetchone()
            if active >= opts.get('workers', 3):
                return 'deferred: active ticket limit'
            db.execute('UPDATE ticket_run SET running=1, session=? WHERE id=?', (assignment_sha, key))
            role = ('requirements', 'design', 'develop', 'test', 'review', 'deploy')[index]
            return {'stage': stage, 'target_sha': assignment_sha, 'agent': 'vibeops-' + role, 'worktree': str(assignment_folder), 'assignment': row['gate']}
        except Exception:
            db.rollback()
            raise
        finally:
            db.commit()


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
