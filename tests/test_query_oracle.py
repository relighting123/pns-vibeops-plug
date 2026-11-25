import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT/'shared/python'))
from oracle_client import query_executor as executor



class Cursor:
    description = [('VALUE',)]
    def __init__(self, rows):
        self.rows = rows
        self.commands = []
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, sql, binds=None):
        self.commands.append((sql, binds))
        self.iterator = iter(self.rows)
    def fetchone(self): return next(self.iterator, None)


class Connection:
    version = 'test-double-not-real-oracle'
    def __init__(self, rows):
        self.cur = Cursor(rows)
        self.closed = self.rolled_back = False
    def cursor(self): return self.cur
    def rollback(self): self.rolled_back = True
    def close(self): self.closed = True


class OracleTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {'SDLC_DATA_ROLE':'develop'})
        env.start()
        self.addCleanup(env.stop)
        from execution_policy.local_role import principal
        self.profile = {'mode':'thin','role_access':{'develop':{principal():['read']}}}

    def test_bound_rows_batch_connection_and_cleanup(self):
        conn = Connection([(1,), (2,), (3,)])
        result = executor.run_batch({**self.profile, 'max_rows':2},
                                    [{'action':'check'}, {'action':'check'}], lambda _:conn)
        self.assertEqual(conn.cur.commands[0][0], 'SET TRANSACTION READ ONLY')
        self.assertTrue(all(r['truncated'] for r in result['results']))
        self.assertEqual(result['results'][0]['rows'], [[1],[2]])
        self.assertTrue(conn.closed and conn.rolled_back)

    def test_validation_precedes_connection(self):
        def forbidden(_): self.fail('No connection should be opened')
        for request in [{'action':'query', 'query':'unregistered'},
                        {'action':'describe','owner':'SECRET','table':'T'},
                        {'action':'check','max_rows':999999}]:
            with self.assertRaises(executor.QueryError):
                executor.run_batch(self.profile,[request], forbidden)

    def test_catalog_binds_are_not_interpolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'queries.json'
            path.write_text(json.dumps({'lookup':{'effect':'read','sql':'SELECT :value FROM dual','binds':['value']}}))
            profile={'queries_file':str(path),'allowed_queries':['lookup']}
            value="x' OR '1'='1"
            sql, binds, _ = executor.query_spec(profile,{'action':'query','query':'lookup','binds':{'value':value}})
            self.assertNotIn(value,sql)
            self.assertEqual(binds['value'],value)
            with self.assertRaises(executor.QueryError):
                executor.query_spec(profile,{'action':'query','query':'lookup','binds':{}})

    def test_data_budget_and_lob_omission(self):
        conn=Connection([('x'*600,)])
        result=executor.run_batch({**self.profile,'max_result_bytes':512},[{'action':'check'}],lambda _:conn)
        self.assertTrue(result['results'][0]['truncated'])
        self.assertEqual(result['results'][0]['rows'],[])
        class LOB:
            def read(self): raise AssertionError('LOB must not be fetched')
        self.assertEqual(executor.cell(LOB()),{'omitted_type':'LOB'})

    def test_execution_failure_closes_connection(self):
        conn=Connection([])
        def fail(*args): raise RuntimeError('failed')
        conn.cur.execute=fail
        with self.assertRaises(RuntimeError):
            executor.run_batch(self.profile,[{'action':'check'}],lambda _:conn)
        self.assertTrue(conn.closed and conn.rolled_back)

    def test_profile_env_and_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            config=Path(tmp)/'profiles.json'
            config.write_text(json.dumps({'databases':{'dev':{'mode':'thin','dsn_env':'TEST_DSN','user_env':'TEST_USER','password_env':'TEST_PASSWORD'}}}))
            with patch.dict(os.environ,{'TEST_DSN':'dsn','TEST_USER':'user','TEST_PASSWORD':'secret'}):
                self.assertEqual(executor.load_profile(config,'dev')['mode'],'thin')
            with self.assertRaises(executor.QueryError): executor.load_profile(config,'missing')

    def test_skill_name_and_knowledge_links(self):
        skill=ROOT/'skills/vibeops-read-oracle-data'
        body=(skill/'SKILL.md').read_text()
        self.assertIn('name: vibeops-read-oracle-data',body)
        for filename in ['execution.md','connections.md','query-rules.md']:
            self.assertTrue((skill/'references'/filename).is_file())
            self.assertIn('references/'+filename,body)
