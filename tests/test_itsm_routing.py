import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/vibeops-orchestrate-sdlc/scripts'))
import gitlab_issue_sync as sync


class RoutingTests(unittest.TestCase):
    def test_mixed_batch_and_changed_destination(self):
        posts = []
        issues = {}

        def respond(request):
            if request.method == 'GET':
                return httpx.Response(200, json=issues.get((request.url.path, request.url.params['labels']), []))
            payload = json.loads(request.content)
            issues[request.url.path, payload['labels']] = [dict(payload, iid=1, web_url=str(request.url))]
            posts.append((request.url.host, request.url.path))
            return httpx.Response(201, json={'iid': 1, 'web_url': str(request.url)})

        def client(config):
            return httpx.Client(base_url=config['gitlab_url'] + '/api/v4/',
                                transport=httpx.MockTransport(respond))

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            routes = [{'target_system': name, 'gitlab_url': 'https://' + name + '.invalid',
                       'project_id': i} for i, name in enumerate(('a', 'b'), 1)]
            registry = root / 'routes'
            registry.write_text(json.dumps(routes + [dict(routes[0], target_system='dup')] * 2))
            (root / 'config').write_text(json.dumps({'routing_file': 'routes', 'batch_size': 10,
                'source': 'test', 'oldest_first': True}))
            rows = [dict(target_system=name, request_id=str(i), revision='1', title='t', summary='s')
                    for i, name in enumerate(('a', 'missing', 'dup', 'b'))]
            for i, row in enumerate(rows):
                row['created_at'] = f'2026-11-25T0{4-i}:00:00+00:00'
            intake = root / 'intake'
            intake.write_text(json.dumps(rows))
            with patch.object(sys, 'argv', ['sync', '--config', str(root / 'config'), '--intake', str(intake)]), patch.object(sync, 'open_client', client), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(sync.main(), 1)
                self.assertEqual(posts, [('b.invalid', '/api/v4/projects/2/issues'),
                                         ('a.invalid', '/api/v4/projects/1/issues')])
                intake.write_text(json.dumps([dict(rows[0], target_system='b')]))
                self.assertEqual(sync.main(), 1)
                self.assertEqual(len(posts), 2)
