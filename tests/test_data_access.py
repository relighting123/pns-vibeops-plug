import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shared/python'))
from execution_policy.local_role import principal
from execution_policy import PolicyError
from http_client import HttpClient
from oracle_client.write_executor import run_write, CommitUnknown
from oracle_client.common import QueryError


def operation(effect='read', method='GET'):
    return {'effect':effect,'method':method,'path':'/items/{id}','retry_safe':True,
            'response_fields':['id'], 'request_schema':{
                'type':'object','required':['path','query','body'],'additionalProperties':False,
                'properties':{'path':{'type':'object','required':['id'],'additionalProperties':False,
                                      'properties':{'id':{'type':'string'}}},
                              'query':{'type':'object','additionalProperties':False},'body':{'type':'null'}}}}


class HttpTests(unittest.TestCase):
    def setUp(self):
        role = patch.dict(os.environ, {'SDLC_DATA_ROLE':'test'})
        role.start()
        self.addCleanup(role.stop)
        self.env=patch.dict(os.environ,{'TEST_HTTP_URL':'https://service.invalid','TEST_HTTP_TOKEN':'do-not-print'})
        self.env.start();self.addCleanup(self.env.stop)
        self.profile={'role_access':{'test':{principal():['read','write']}},'base_url_env':'TEST_HTTP_URL','auth':{'type':'bearer','token_env':'TEST_HTTP_TOKEN'},
                      'allowed_operations':['op'],'max_read_attempts':2,'allow_write':True}
        self.req={'operation':'op','path':{'id':'item'}}

    def test_wrong_role_denied_before_transport(self):
        with patch.dict(os.environ, {'SDLC_DATA_ROLE':'unassigned'}):
            with HttpClient(self.profile, {'op':operation()}, transport=httpx.MockTransport(
                    lambda req: self.fail('unexpected request'))) as client:
                with self.assertRaises(PolicyError):
                    client.request(self.req)

    def test_read_retry_connection_and_projection(self):
        calls=[];waits=[]
        def handler(req):
            calls.append(req)
            self.assertEqual(req.headers['Authorization'],'Bearer do-not-print')
            return httpx.Response(503 if len(calls)==1 else 200,json={'id':'item','large':'unused'})
        with HttpClient(self.profile,{'op':operation()},transport=httpx.MockTransport(handler),sleep=waits.append) as c:
            result=c.request(self.req)
            self.assertEqual(result['body'],{'id':'item'})
            self.assertEqual(result['attempts'],2)
            self.assertEqual(len(waits),1)
        self.assertTrue(c.client.is_closed)

    def test_invalid_schema_and_path_do_not_call_transport(self):
        def forbidden(req): self.fail('Transport must not run')
        with HttpClient(self.profile,{'op':operation()},transport=httpx.MockTransport(forbidden)) as c:
            for req in [dict(self.req, query={'unknown':1}),dict(self.req,path={'id':'../secret'}),dict(self.req,operation='other')]:
                with self.assertRaises(PolicyError): c.request(req)

    def test_write_requires_three_conditions(self):
        def forbidden(req): self.fail('No network before policy acceptance')
        with HttpClient(self.profile,{'op':operation('write','POST')},transport=httpx.MockTransport(forbidden)) as c:
            with self.assertRaises(PolicyError): c.request(self.req,effect='read')
            with self.assertRaises(PolicyError): c.request(self.req,effect='write')
        with HttpClient(dict(self.profile,allow_write=False),{'op':operation('write','POST')},transport=httpx.MockTransport(forbidden)) as c:
            with self.assertRaises(PolicyError): c.request(self.req,effect='write',apply=True)

    def test_unknown_write_never_retried(self):
        calls=[]
        def handler(req):
            calls.append(req)
            raise httpx.ReadTimeout('internal-secret',request=req)
        with HttpClient(self.profile,{'op':operation('write','POST')},transport=httpx.MockTransport(handler)) as c:
            result=c.request(self.req,effect='write',apply=True)
        self.assertEqual(len(calls),1)
        self.assertEqual(result['outcome'],'unknown')
        self.assertNotIn('internal-secret',json.dumps(result))

    def test_post_read_and_no_redirect(self):
        def handler(req):
            self.assertEqual(req.method,'POST')
            return httpx.Response(302,headers={'Location':'https://untrusted.invalid/'})
        with HttpClient(self.profile,{'op':operation('read','POST')},transport=httpx.MockTransport(handler)) as c:
            result=c.request(self.req)
        self.assertFalse(result['ok']);self.assertEqual(result['status'],302)

    def test_response_budget(self):
        def handler(req):return httpx.Response(200,json={'id':'x'*1000})
        with HttpClient(dict(self.profile,max_response_bytes=512),{'op':operation()},transport=httpx.MockTransport(handler)) as c:
            result=c.request(self.req)
        self.assertTrue(result['truncated']);self.assertIsNone(result['body'])


class WriteConnection:
    version='fake'
    def __init__(self, rows=1, commit_error=False):
        self.rowcount=rows;self.commit_error=commit_error;self.committed=False;self.rolled_back=False;self.closed=False
    def cursor(self):return self
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def execute(self,sql,binds):self.executed=(sql,binds)
    def commit(self):
        if self.commit_error:raise OSError('lost ack')
        self.committed=True
    def rollback(self):self.rolled_back=True
    def close(self):self.closed=True


class OracleWriteTests(unittest.TestCase):
    def setUp(self):
        role = patch.dict(os.environ, {'SDLC_DATA_ROLE':'test'})
        role.start()
        self.addCleanup(role.stop)
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        p=Path(tmp.name)/'writes.json';p.write_text(json.dumps({'update':{'effect':'write','sql':'UPDATE t SET v=:v WHERE id=:id','binds':['id','v']}}))
        self.profile={'role_access':{'test':{principal():['read','write']}},'mode':'thin','writes_file':str(p),'allowed_writes':['update'],'allow_write':True}
        self.request={'operation':'update','binds':{'id':1,'v':'new'},'expected_rows':1}
    def test_matching_count_commits(self):
        c=WriteConnection();result=run_write(self.profile,self.request,True,lambda _:c)
        self.assertEqual(result['outcome'],'committed');self.assertTrue(c.committed and c.closed)
    def test_mismatch_rolls_back(self):
        c=WriteConnection(rows=2)
        with self.assertRaises(QueryError):run_write(self.profile,self.request,True,lambda _:c)
        self.assertTrue(c.rolled_back and c.closed);self.assertFalse(c.committed)
    def test_apply_guard_before_connect(self):
        def forbidden(_):self.fail('No connection before --apply')
        with self.assertRaises(PolicyError):run_write(self.profile,self.request,False,forbidden)
    def test_commit_loss_is_unknown(self):
        c=WriteConnection(commit_error=True)
        with self.assertRaises(CommitUnknown):run_write(self.profile,self.request,True,lambda _:c)
        self.assertTrue(c.closed)


class ImportTests(unittest.TestCase):
    def test_all_entrypoints_resolve_shared_imports_from_other_directory(self):
        for service in ('oracle','iflow','cube'):
            for action in ('read','modify'):
                p=ROOT/f'skills/vibeops-{action}-{service}-data/scripts/{service}_client.py'
                result=subprocess.run([sys.executable,str(p),'--help'],cwd='/tmp',capture_output=True,text=True,timeout=10)
                self.assertEqual(result.returncode,0,result.stderr)
