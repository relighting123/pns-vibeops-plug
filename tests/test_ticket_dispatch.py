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
from ticket_dispatch import REVIEW_DONE, REVIEW_WAITING, dispatch_batch


class Response:
    def __init__(self, data):
        self.data = data
        self.headers = {}

    def json(self):
        return self.data

    def raise_for_status(self):
        pass


class GitLab:
    base_url = 'https://test.example/api/v4/'

    def __init__(self):
        self.notes = {}
        self.mr = None
        self.active = set()
        self.statuses = {}
        self.uploads = []

    def get(self, path, params=None):
        if path.endswith('/notes'):
            return Response(self.notes.get(path, [])[::-1])
        if path == 'user':
            return Response({'id': 1})
        if path.endswith('/issues'):
            return Response(list(self.active))
        if path == 'projects/1':
            return Response({'id': 1, 'default_branch': 'main', 'path_with_namespace': 'org/app', 'web_url': 'https://test.example/org/app'})
        if path.endswith('/merge_requests'):
            return Response([self.mr] if self.mr else [])
        if '/merge_requests/' in path:
            return Response(self.mr)
        return Response({'state': 'opened', 'title': 'ITSM request', 'labels': (['vibeops-running'] if path in self.active else [])})

    def post(self, path, json=None, files=None):
        if path.endswith('/uploads'):
            self.uploads.append(files['file'])
            return Response({'url': '/uploads/123abc/' + files['file'][0]})
        if path.endswith('/api/graphql'):
            variables = json['variables']
            if 'iid' in variables:
                iid = variables['iid']
                return Response({'data': {'namespace': {'workItem': self.work_item(iid)}}})
            iid = variables['id'].rsplit('/', 1)[-1]
            self.set_status(f'projects/1/issues/{iid}', 1, variables['name'])
            return Response({'data': {'workItemUpdate': {'errors': [], 'workItem': self.work_item(iid)}}})
        if path.endswith('/merge_requests'):
            self.mr = dict(json, iid=1, source_project_id=1, state='opened',
                           web_url='https://test.example/org/app/-/merge_requests/1')
            return Response(self.mr)
        return Response(self.comment(path, 1, json['body']))

    def put(self, path, json):
        if '/issues/' in path:
            if 'add_labels' in json:
                self.active.add(path)
            else:
                self.active.discard(path)
            return Response({})
        self.mr.update(json)
        return Response(self.mr)

    def work_item(self, iid):
        name = self.statuses.get(f'projects/1/issues/{iid}', 'To do')
        category = 'TO_DO' if name == 'To do' else 'IN_PROGRESS'
        return {'id': f'gid://gitlab/WorkItem/{iid}',
                'widgets': [{'status': {'name': name, 'category': category}}]}

    def set_status(self, path, actor, name=REVIEW_DONE):
        self.statuses[path] = name
        note = self.comment(path + '/notes', actor, f'set status to {name}')
        note['system'] = True

    def comment(self, path, author, body):
        notes = self.notes.setdefault(path, [])
        note = {'id': len(notes) + 1, 'author': {'id': author}, 'body': body}
        notes.append(note)
        return note


class TicketTest(unittest.TestCase):
    def test_three_tickets_two_approved_and_resume(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root) / 'repo'
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            for args in [('config', 'user.name', 'Test'), ('config', 'user.email', 't@example.net'),
                         ('commit', '--allow-empty', '-qm', 'base')]:
                subprocess.run(['git', *args], cwd=repo, check=True)
            cfg = {'project_id': 1, 'token_env': 'TEST_TOKEN',
                   'dispatch': {'repository': str(repo), 'worktrees': root+'/trees', 'base_ref': 'HEAD',
                                'approvers': {'analyze-requirements': [9], 'design-system': [9]}}}
            tickets = [{'iid': i, 'revision': 'v1'} for i in (1, 2, 3)]
            api = GitLab()
            def approve(i):
                api.set_status(f'projects/1/issues/{i}', 9)
            api.set_status('projects/1/issues/2', 9)
            dispatch_batch(api, cfg, tickets)
            api.set_status('projects/1/issues/2', 10)
            api.comment('projects/1/issues/2/notes', 9, 'done')
            api.comment('projects/1/issues/2/notes', 9, 'approve')
            approve(1)
            approve(3)
            result = dispatch_batch(api, cfg, tickets)
            first = result[0]['dispatch']
            self.assertEqual(first['agent'], 'vibeops-requirements')
            self.assertEqual(result[2]['dispatch']['agent'], first['agent'])
            self.assertNotEqual(first['worktree'], result[2]['dispatch']['worktree'])
            self.assertEqual(result[1]['dispatch'], 'waiting for analyze-requirements')
            api.set_status('projects/1/issues/2', 9, REVIEW_WAITING)
            approve(2)
            cfg['dispatch']['workers'] = 2
            self.assertIn('deferred', dispatch_batch(api, cfg, tickets)[1]['dispatch'])
            folder = Path(first['worktree'])
            checkpoint = folder / 'artifacts/sdlc-progress.md'
            checkpoint.parent.mkdir(exist_ok=True)
            checkpoint.write_text('requirements reviewed')
            subprocess.run(['git', 'add', '.'], cwd=folder, check=True)
            subprocess.run(['git', 'commit', '-qm', 'stage'], cwd=folder, check=True)
            result = dispatch_batch(api, cfg, tickets[:1], first['assignment'])
            self.assertIn('stage report required', result[0]['dispatch'])
            Path(first['report_path']).write_text('# Requirements')
            subprocess.run(['git', 'add', '.'], cwd=folder, check=True)
            subprocess.run(['git', 'commit', '-qm', 'report'], cwd=folder, check=True)
            remote = Path(root) / 'remote.git'
            subprocess.run(['git', 'init', '--bare', '-q', str(remote)], check=True)
            with patch('ticket_dispatch.project_remote', return_value=str(remote)):
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
            cfg = dict(project_id=1, dispatch=opts)
            api = GitLab()
            def tick(token=None):
                return dispatch(api, cfg, dict(iid=1, revision='v1'), token)
            remote = Path(tmp) / 'remote.git'
            git(tmp, 'init', '--bare', '-q', str(remote))
            remote_patch = patch('ticket_dispatch.project_remote', return_value=str(remote))
            remote_patch.start()
            self.addCleanup(remote_patch.stop)
            for stage in STAGES:
                if stage == 'deploy-release':
                    self.assertEqual(tick(), 'waiting for merge')
                    git(repo, 'checkout', '-qb', 'integration', verified)
                    git(repo, 'commit', '--allow-empty', '-qm', 'merge commit')
                    merged = subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                                                     cwd=repo, text=True).strip()
                    git(repo, 'push', str(remote), 'HEAD:refs/heads/main')
                    api.mr.update(state='merged', merge_commit_sha=merged)
                if stage == 'implement-feature':
                    self.assertEqual(tick(), 'waiting for design signoff')
                    self.assertIsNone(api.mr)
                    issue_notes = api.notes['projects/1/issues/1/notes']
                    self.assertIn('/-/blob/', issue_notes[-2]['body'])
                    self.assertIn('/artifacts/vibeops/design.md', issue_notes[-2]['body'])
                    api.set_status('projects/1/issues/1', 9)
                else:
                    self.assertEqual(tick(), 'waiting for '+stage)
                    api.set_status('projects/1/issues/1', 9)
                assignment = tick()
                folder = Path(assignment['worktree'])
                token = assignment['assignment']
                Path(assignment['report_path']).write_text(f'# {stage}')
                if stage in STAGES[:3]:
                    artifact = folder / 'artifacts/sdlc-progress.md'
                    artifact.parent.mkdir(exist_ok=True)
                    artifact.write_text(stage)
                    git(folder, 'add', '.')
                    git(folder, 'commit', '-qm', stage)
                if stage == 'implement-feature':
                    self.assertTrue(api.mr['title'].startswith('Draft:'))
                    self.assertIn('이슈 #1', api.mr['description'])
                    api.mr['sha'] = subprocess.check_output(
                        ['git', 'rev-parse', 'HEAD'], cwd=folder, text=True).strip()
                if stage == 'verify-change':
                    opts['verify_command'] = [sys.executable, '-c', 'raise SystemExit(1)']
                    self.assertIn('verification failed', tick(token))
                    opts['verify_command'] = [sys.executable, '-c', 'pass']
                    verified = assignment['target_sha']
                if stage == 'deploy-release':
                    self.assertEqual(assignment['target_sha'], merged)
                    self.assertNotEqual(assignment['target_sha'], verified)
                    self.assertIn('-deploy-', folder.name)
                self.assertEqual(tick(token), stage+' completed')
            self.assertEqual([upload[0] for upload in api.uploads],
                             ['test-results.md', 'review.md', 'release.md'])
