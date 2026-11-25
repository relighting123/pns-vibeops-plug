from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/vibeops-orchestrate-sdlc/scripts'))
from ticket_dispatch import dispatch_batch


class Response:
    def __init__(self, data):
        self.data = data

    def json(self):
        return self.data

    def raise_for_status(self):
        pass


class GitLab:
    base_url = 'https://test.example/api/v4/'

    def __init__(self):
        self.notes = {}

    def get(self, path, params=None):
        return Response(self.notes.get(path, []) if params else {'state': 'opened'})

    def post(self, path, json):
        self.notes.setdefault(path, []).append({'author': {'id': 1}, 'body': json['body']})
        return Response({})


class TicketTest(unittest.TestCase):
    def test_three_tickets_two_approved_and_resume(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root) / 'repo'
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            for args in [('config', 'user.name', 'Test'), ('config', 'user.email', 't@example.net'),
                         ('commit', '--allow-empty', '-qm', 'base')]:
                subprocess.run(['git', *args], cwd=repo, check=True)
            cfg = {'project_id': 1, 'token_env': 'TEST_TOKEN', 'state_db': root+'/db',
                   'dispatch': {'repository': str(repo), 'worktrees': root+'/trees', 'base_ref': 'HEAD',
                                'approvers': {'analyze-requirements': [9], 'design-system': [9]}}}
            tickets = [{'iid': i, 'revision': 'v1'} for i in (1, 2, 3)]
            api = GitLab()
            def approve(i):
                notes = api.notes[f'projects/1/issues/{i}/notes']
                notes.append({'author': {'id': 9}, 'body': notes[-1]['body'].splitlines()[-1]})
            dispatch_batch(api, cfg, tickets)
            approve(1)
            approve(3)
            result = dispatch_batch(api, cfg, tickets)
            first = result[0]['dispatch']
            self.assertEqual(first['agent'], 'vibeops-requirements')
            self.assertEqual(result[2]['dispatch']['agent'], first['agent'])
            self.assertNotEqual(first['worktree'], result[2]['dispatch']['worktree'])
            self.assertEqual(result[1]['dispatch'], 'waiting for analyze-requirements')
            approve(2)
            cfg['dispatch']['workers'] = 2
            self.assertIn('deferred', dispatch_batch(api, cfg, tickets)[1]['dispatch'])
            folder = Path(first['worktree'])
            checkpoint = folder / 'artifacts/sdlc-progress.md'
            checkpoint.parent.mkdir()
            checkpoint.write_text('requirements reviewed')
            subprocess.run(['git', 'add', '.'], cwd=folder, check=True)
            subprocess.run(['git', 'commit', '-qm', 'stage'], cwd=folder, check=True)
            result = dispatch_batch(api, cfg, tickets[:1], first['assignment'])
            self.assertEqual(result[0]['dispatch'], 'analyze-requirements completed')
            self.assertEqual(dispatch_batch(api, cfg, tickets[:1], first['assignment'])[0]['dispatch'], 'stale completion')
            self.assertIsInstance(dispatch_batch(api, cfg, tickets)[1]['dispatch'], dict)

    def test_release_requires_successful_verification_of_exact_commit(self):
        from ticket_dispatch import STAGES, dispatch
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            def git(folder, *args):
                subprocess.run(['git', *args], cwd=folder, check=True)
            git(repo, 'config', 'user.name', 'Test')
            git(repo, 'config', 'user.email', 'test@example.org')
            git(repo, 'commit', '--allow-empty', '-qm', 'base')
            opts = dict(repository=str(repo), worktrees=tmp+'/trees', base_ref='HEAD',
                        deployment=True, approvers={s: [9] for s in STAGES})
            cfg = dict(project_id=1, state_db=tmp+'/db', dispatch=opts)
            api = GitLab()
            def tick(token=None):
                return dispatch(api, cfg, dict(iid=1, revision='v1'), token)
            for stage in STAGES:
                self.assertEqual(tick(), 'waiting for '+stage)
                notes = api.notes['projects/1/issues/1/notes']
                notes.append(dict(author=dict(id=9), body=notes[-1]['body'].splitlines()[-1]))
                assignment = tick()
                folder = Path(assignment['worktree'])
                token = assignment['assignment']
                if stage in STAGES[:3]:
                    artifact = folder / 'artifacts/sdlc-progress.md'
                    artifact.parent.mkdir(exist_ok=True)
                    artifact.write_text(stage)
                    git(folder, 'add', '.')
                    git(folder, 'commit', '-qm', stage)
                if stage == 'verify-change':
                    opts['verify_command'] = [sys.executable, '-c', 'raise SystemExit(1)']
                    self.assertIn('verification failed', tick(token))
                    opts['verify_command'] = [sys.executable, '-c', 'pass']
                    verified = assignment['target_sha']
                if stage == 'deploy-release':
                    self.assertEqual(assignment['target_sha'], verified)
                    git(folder, 'commit', '--allow-empty', '-qm', 'new revision')
                    self.assertIn('fresh approval required', tick(token))
                    self.assertEqual(tick(), 'waiting for verify-change')
                    break
                self.assertEqual(tick(token), stage+' completed')
