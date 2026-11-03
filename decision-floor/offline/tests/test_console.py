"""End-to-end localhost console coverage, including source version replay."""
import base64
import http.client
import json
import shutil
import tempfile
from pathlib import Path
import threading
import unittest
from http.server import ThreadingHTTPServer

from app import make_handler,prepare_project,scan,get_summary,safe_mapping

PACKAGE=Path(__file__).resolve().parents[1]


class OfflineConsoleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project=prepare_project(Path(self.tmp.name)/'client')
        self.token='local-evaluation-test-token'
        self.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.project,self.token,threading.RLock()))
        self.addCleanup(self.server.server_close)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
    def call(self,method,path,body=None,authorized=True,extra_headers=None):
        h={'X-Local-Token':self.token} if authorized else {}
        if body is not None:
            h['Content-Type']='application/json';body=json.dumps(body)
        h.update(extra_headers or {})
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=12)
        try:
            conn.request(method,path,body=body,headers=h)
            res=conn.getresponse();payload=res.read();return res.status,res.getheaders(),payload
        finally:conn.close()
    def decode(self,status_headers_body):
        status,_,data=status_headers_body
        return status,json.loads(data)
    def test_access_control_and_bootstrap(self):
        self.assertEqual(self.call('GET','/api/summary',authorized=False)[0],403)
        self.assertEqual(self.call('POST','/api/scan',{},authorized=False)[0],403)
        self.assertEqual(self.call('GET','/',authorized=False)[0],403)
        status,_,html=self.call('GET','/?token='+self.token,authorized=False)
        self.assertEqual(status,200)
        self.assertIn(b'Decision Floor',html)
        self.assertIn(self.token.encode(),html)
        self.assertEqual(self.call('GET','/app.js?token='+self.token,authorized=False)[0],200)
        self.assertEqual(self.call('GET','/style.css?token='+self.token,authorized=False)[0],200)
        self.assertEqual(self.call('GET','/api/export?name=../../etc/passwd')[0],400)
        self.assertEqual(self.call('GET','/api/source?sha256=../../etc/passwd')[0],400)
        self.assertEqual(self.call('POST','/api/scan',{},extra_headers={'Origin':'http://evil.invalid'})[0],403)
        self.assertEqual(self.server.server_address[0],'127.0.0.1')
    def test_new_material_scan_search_replay_and_version_retention(self):
        source=(PACKAGE/'sample_inputs'/'missed'/'sop_decisions.csv').read_bytes()
        data={'filename':'sop_decisions.csv','bytes_base64':base64.b64encode(source).decode()}
        status,result=self.decode(self.call('POST','/api/upload',data))
        self.assertEqual(status,200);self.assertEqual(result['bytes'],len(source))
        status,result=self.decode(self.call('POST','/api/scan',{}))
        self.assertEqual(status,200);self.assertEqual(result['case_count'],1)
        status,summary=self.decode(self.call('GET','/api/summary'))
        self.assertEqual(status,200);self.assertEqual(summary['source_count'],1)
        status,hits=self.decode(self.call('GET','/api/search?q=SOP-017'))
        self.assertEqual(status,200);self.assertTrue(hits['hits'])
        source_hash=hits['hits'][0]['sha256']
        status,_,raw=self.call('GET','/api/source?sha256='+source_hash)
        self.assertEqual(status,200);self.assertEqual(raw,source)
        status,_,html=self.call('GET','/report?token='+self.token,authorized=False)
        self.assertEqual(status,200);self.assertIn(b'SOP-017',html)
        # Different bytes under the same filename: first source is archived BEFORE overwrite.
        replacement=source.replace(b'7000',b'8000')
        changed={'filename':'sop_decisions.csv','bytes_base64':base64.b64encode(replacement).decode()}
        self.assertEqual(self.call('POST','/api/upload',changed)[0],200)
        status,res=self.decode(self.call('POST','/api/scan',{}))
        self.assertEqual(status,200)
        status,summary=self.decode(self.call('GET','/api/summary'))
        self.assertEqual(status,200);self.assertEqual(summary['source_count'],2)
        self.assertEqual(self.call('GET','/api/source?sha256='+source_hash)[2],source)
        self.assertEqual(self.decode(self.call('GET','/api/verify'))[1]['status'],'PASS')
    def test_reviewer_cannot_close_an_investigation(self):
        shutil.copytree(PACKAGE/'sample_inputs'/'missed',self.project/'incoming',dirs_exist_ok=True)
        self.assertEqual(self.call('POST','/api/scan',{})[0],200)
        summary=self.decode(self.call('GET','/api/summary'))[1]
        q=summary['questions'][0]
        payload={'case_key':q['case_key'],'code':q['code'],'actor':'QA tester',
                 'disposition':'reviewed','note':'The documented source of the delay is still not verified.'}
        status,review=self.decode(self.call('POST','/api/review',payload))
        self.assertEqual(status,200);self.assertEqual(len(review['sha256']),64)
        reviews=self.decode(self.call('GET','/api/reviews'))[1]['reviews']
        self.assertEqual(len(reviews),1)
        self.assertTrue(any(x['code']==q['code'] for x in self.decode(self.call('GET','/api/summary'))[1]['questions']))
        payload['disposition']='closed'
        self.assertEqual(self.call('POST','/api/review',payload)[0],400)
        payload['code']='FAKE'
        payload['disposition']='reviewed'
        self.assertEqual(self.call('POST','/api/review',payload)[0],400)
    def test_mapping_validation_and_live_reload(self):
        status,mapping=self.decode(self.call('GET','/api/config'))
        self.assertEqual(status,200)
        self.assertEqual(self.call('POST','/api/config',{'mapping':mapping})[0],200)
        m=json.loads(json.dumps(mapping));m['sources'][0]['pattern']='../secrets.csv'
        self.assertEqual(self.call('POST','/api/config',{'mapping':m})[0],400)
        m=json.loads(json.dumps(mapping));m['sources'][0]['kind']='telepathy'
        self.assertEqual(self.call('POST','/api/config',{'mapping':m})[0],400)
        self.assertEqual(self.decode(self.call('GET','/api/config'))[1]['sources'][0]['kind'],'forecast')
    def test_intake_filename_and_size_defenses(self):
        for name in ('../secrets.csv','..hidden.csv','folder/data.csv','data.exe'):
            self.assertEqual(self.call('POST','/api/upload',{'filename':name,'bytes_base64':base64.b64encode(b'x').decode()})[0],400)
        self.assertEqual(self.call('POST','/api/upload',{'filename':'good.csv','bytes_base64':'#$&*'})[0],400)
        self.assertEqual(self.call('POST','/api/upload',{'filename':'good.csv','bytes_base64':base64.b64encode(b'a'*8_000_001).decode()})[0],400)

if __name__=='__main__':unittest.main()
