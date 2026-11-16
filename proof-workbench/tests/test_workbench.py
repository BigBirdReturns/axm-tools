"""Orchestration boundaries, separate from native donor acceptance."""
import copy,hashlib,importlib.util,json,os,stat,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('proof',ROOT/'proof.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def example():return json.loads((ROOT/'engagement.example.json').read_text())
def ready():
 e=example();e.update(target_decision='Reconstruct a corrected decision',receiving_owner='Receiving reviewer',data_custodian='Data owner',data_authorized=True,acceptance_criteria=['Cold replay','Reject changed source']);return e
class WorkbenchTests(unittest.TestCase):
 def test_example_held(self):
  p=m.plan(example());self.assertEqual(p['state'],'HELD');self.assertEqual(len(p['holds']),5)
 def test_ready_is_scoping_only(self):
  p=m.plan(ready());self.assertEqual(p['state'],'READY_FOR_SCOPING');self.assertFalse(p['execute_allowed']);self.assertFalse(p['publish_allowed']);self.assertEqual(p['customer_acceptance'],'NOT_ESTABLISHED')
 def test_each_permission_hold(self):
  for key,value in [('target_decision',''),('receiving_owner',''),('data_custodian',''),('data_authorized',False),('acceptance_criteria',[])]:
   with self.subTest(key=key):e=ready();e[key]=value;self.assertIn(key,m.plan(e)['holds'])
 def test_unrecognized_adapter(self):
  e=ready();e['adapter']='shell';self.assertRaises(m.Refusal,m.plan,e)
 def test_shell_injection_is_no_command(self):
  e=ready();e['target_decision']='$(touch /tmp/never-executed)';p=m.plan(e);self.assertFalse(p['execute_allowed'])
 def test_extra_fields_refused(self):
  for field in ['command','endpoint','api_key','public','production_authority']:
   with self.subTest(field=field):e=ready();e[field]='x';self.assertRaises(m.Refusal,m.plan,e)
 def test_unauthorized_publication_refused(self):
  e=ready();e['disclosure']='public';self.assertRaises(m.Refusal,m.plan,e)
 def test_unknown_evidence(self):
  e=ready();e['evidence_class']='certified';self.assertRaises(m.Refusal,m.plan,e)
 def test_permission_boolean_not_string(self):
  for v in ['true',1,None]:
   with self.subTest(v=v):e=ready();e['data_authorized']=v;self.assertRaises(m.Refusal,m.plan,e)
 def test_criteria_required_and_typed(self):
  for v in [None,'passed',[False],[''],['   '],[1]]:
   with self.subTest(v=v):e=ready();e['acceptance_criteria']=v;self.assertRaises(m.Refusal,m.plan,e)
 def test_id_path_refusal(self):
  for v in ['../escape','a/b','', 'aa', 'a'*81, 'x;exit']:
   with self.subTest(v=v):e=ready();e['case_id']=v;self.assertRaises(m.Refusal,m.plan,e)
 def test_cost_formula(self):
  e=example()['economics'];e.update(price=10000,engineering_hours=20,hourly_cost=100,compute_cost=100,support_reserve=900)
  r=m.economics(e);self.assertEqual(r['estimated_delivery_cost'],3000);self.assertEqual(r['estimated_contribution'],7000);self.assertEqual(r['estimated_margin_percent'],70)
 def test_zero_price_has_unknown_margin(self):self.assertIsNone(m.economics(example()['economics'])['estimated_margin_percent'])
 def test_loss_not_hidden(self):
  e=example()['economics'];e.update(price=1,support_reserve=10);self.assertEqual(m.economics(e)['estimated_contribution'],-9)
 def test_invalid_numbers(self):
  for v in [-1,True,None,'10',float('nan'),float('inf'),10**400]:
   with self.subTest(v=str(v)[:30]):e=example()['economics'];e['price']=v;self.assertRaises(m.Refusal,m.economics,e)
 def test_derived_overflow(self):
  e=example()['economics'];e.update(price=1e-310,engineering_hours=1e12,hourly_cost=1e12);self.assertRaises(m.Refusal,m.economics,e)
 def test_currency_required(self):
  e=example()['economics'];del e['currency'];self.assertRaises(m.Refusal,m.economics,e)
 def test_duplicate_json(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'x.json';p.write_text('{"x":1,"x":2}');self.assertRaises(m.Refusal,m.load,p)
 def test_nonfinite_json(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'x.json';p.write_text('{"x":NaN}');self.assertRaises(m.Refusal,m.load,p)
 def test_json_size(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'x.json';p.write_bytes(b' '*(m.MAX_JSON+1));self.assertRaises(m.Refusal,m.load,p)
 def test_unsafe_paths(self):
  for p in ['../x','/x','a/../x','C:/x','a\\b','a//b','a/./b','x\0y']:
   with self.subTest(p=p):self.assertRaises(m.Refusal,m.safe_relative,p)
 def test_valid_relative(self):self.assertEqual(str(m.safe_relative('a/b.json')),'a/b.json')
 def test_archive_traversal(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'evil.zip'
   with zipfile.ZipFile(p,'w') as z:z.writestr('../escape','NO')
   self.assertRaises(m.Refusal,m.extract,p,Path(t)/'out');self.assertFalse((Path(t)/'escape').exists())
 def test_archive_symlink(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'evil.zip'
   with zipfile.ZipFile(p,'w') as z:
    i=zipfile.ZipInfo('link');i.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(i,'/etc/passwd')
   self.assertRaises(m.Refusal,m.extract,p,Path(t)/'out')
 def test_duplicate_archive(self):
  import warnings
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'evil.zip'
   with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    with zipfile.ZipFile(p,'w') as z:z.writestr('x','1');z.writestr('x','2')
   self.assertRaises(m.Refusal,m.extract,p,Path(t)/'out')
 def test_archive_existing_directory(self):
  with tempfile.TemporaryDirectory() as t:self.assertRaises(FileExistsError,m.extract,ROOT/'sources/i3x.zip',Path(t))
 def test_all_three_source_digests(self):
  d=m.load(ROOT/'donor-map.json');self.assertEqual({x['id'] for x in d['donors']},set(m.ADAPTERS))
  for x in d['donors']:self.assertEqual(m.sha((ROOT/x['path']).read_bytes()),x['sha256'])
 def test_native_formats_preserved(self):
  with zipfile.ZipFile(ROOT/'sources/i3x.zip') as z:self.assertIn(b'axm-i3x-proof/0.1.0',z.read('cesmii-proof/engine.js'))
  with zipfile.ZipFile(ROOT/'sources/receptionist.zip') as z:self.assertIn('AXM-BOSC-Replay/engine/pre-repair-v1/worker.py',z.namelist())
 def test_internal_manifest(self):self.assertEqual(m.verify()['status'],'PASS')
 def test_wrong_external_digest(self):self.assertRaises(m.Refusal,m.verify,ROOT,'0'*64)
 def test_correct_external_digest(self):self.assertEqual(m.verify(expected=m.sha((ROOT/'MANIFEST.json').read_bytes()))['status'],'PASS')
 def fixture_manifest(self,t):
  p=Path(t);(p/'a.txt').write_bytes(b'original');m.dump(p/'MANIFEST.json',{'schema':'axm-proof-package/1','files':{'a.txt':{'sha256':m.sha(b'original'),'bytes':8}}});return p
 def test_tampered_source(self):
  with tempfile.TemporaryDirectory() as t:p=self.fixture_manifest(t);(p/'a.txt').write_bytes(b'tampered');self.assertRaises(m.Refusal,m.verify,p)
 def test_missing_source(self):
  with tempfile.TemporaryDirectory() as t:p=self.fixture_manifest(t);(p/'a.txt').unlink();self.assertRaises(m.Refusal,m.verify,p)
 def test_extra_executable(self):
  with tempfile.TemporaryDirectory() as t:p=self.fixture_manifest(t);(p/'arbitrary.py').write_text('print(1)');self.assertRaises(m.Refusal,m.verify,p)
 def test_nested_manifest_not_ignored(self):
  with tempfile.TemporaryDirectory() as t:p=self.fixture_manifest(t);(p/'nested').mkdir();(p/'nested/MANIFEST.json').write_text('{}');self.assertRaises(m.Refusal,m.verify,p)
 def test_empty_receipt_refused(self):
  with tempfile.TemporaryDirectory() as t:m.dump(Path(t)/'evidence-manifest.json',{'schema':'axm-proof-run-files/1','files':{}});self.assertRaises(m.Refusal,m.verify_receipt,t)
 def test_run_byte_tamper(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);m.dump(p/'report.json',{'status':'PASS'});r=(p/'report.json').read_bytes();m.dump(p/'evidence-manifest.json',{'schema':'axm-proof-run-files/1','files':{'report.json':{'sha256':m.sha(r),'bytes':len(r)}}});self.assertEqual(m.verify_receipt(p)['status'],'PASS');(p/'report.json').write_text('changed');self.assertRaises(m.Refusal,m.verify_receipt,p)
 def test_scope_preserves_holds(self):
  e=example();s=m.scope_markdown(m.plan(e),e);self.assertIn('HELD',s);self.assertIn('not an executed agreement',s)
if __name__=='__main__':unittest.main()
