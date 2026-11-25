"""Run one approved stage per ticket on a local scheduler tick."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import uuid

STAGES = ('analyze-requirements', 'design-system', 'implement-feature',
          'verify-change', 'review-release', 'deploy-release')


def git(folder, *args):
    return subprocess.check_output(['git', *args], cwd=folder, text=True).strip()


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
            token = f"approve {stage} {row['gate']} {row['head'] or ticket['revision']}"
            notes = client.get(path + '/notes', params={'per_page': 100, 'sort': 'desc'})
            notes.raise_for_status()
            notes = notes.json()
            allowed = opts['approvers'][stage]
            if not any(n['author']['id'] in allowed and n['body'] == token and not n.get('system') for n in notes):
                notice = 'SDLC 승인 요청\n\n' + token
                if not any(n['body'] == notice for n in notes):
                    client.post(path + '/notes', json={'body': notice}).raise_for_status()
                return 'waiting for ' + stage
            branch = 'sdlc/' + key
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
            if completion is not None:
                if stage == 'verify-change':
                    command = opts.get('verify_command')
                    if not isinstance(command, list) or not command or not all(isinstance(v, str) and v for v in command):
                        return 'configure dispatch.verify_command before verification'
                    result = subprocess.run(command, cwd=folder, timeout=600)
                    if result.returncode or git(folder, 'rev-parse', 'HEAD') != head or git(folder, 'status', '--porcelain'):
                        return 'verification failed or checkout changed'
                    db.execute('INSERT OR REPLACE INTO ticket_verification VALUES (?, ?)', (key, head))
                elif not release_stage:
                    if head == row['session']:
                        return 'new stage commit required'
                    git(folder, 'merge-base', '--is-ancestor', row['session'], head)
                    git(folder, 'ls-files', '--error-unmatch', 'artifacts/sdlc-progress.md')
                client.post(path + '/notes', json={'body': f'SDLC {stage} 완료 · {head}'}).raise_for_status()
                db.execute('UPDATE ticket_run SET stage=?, gate=?, head=?, running=0 WHERE id=?',
                           (index + 1, uuid.uuid4().hex, head, key))
                return stage + ' completed'
            if row['head'] and head != row['head']:
                return 'inspect changed checkpoint'
            active, = db.execute('SELECT count(*) FROM ticket_run WHERE running=1').fetchone()
            if active >= opts.get('workers', 3):
                return 'deferred: active ticket limit'
            db.execute('UPDATE ticket_run SET running=1, session=? WHERE id=?', (head, key))
            role = ('requirements', 'design', 'develop', 'test', 'review', 'deploy')[index]
            return {'stage': stage, 'target_sha': head, 'agent': 'vibeops-' + role, 'worktree': str(folder), 'assignment': row['gate']}
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
