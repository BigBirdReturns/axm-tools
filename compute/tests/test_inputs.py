import importlib.util,json,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'inputs'/'collect.py'
spec=importlib.util.spec_from_file_location('input_collector',P); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Inputs(unittest.TestCase):
 def ha(self,**kw):
  row={'Specs':{'gpus':[{'manufacturer':'AMD','model':'MI300X','count':1}]},'OnDemandPrice':299,'MinimumReservationMinutes':60,'Quantity':1};row.update(kw)
  return m.normalize_hotaisle([row],'2026-09-24T19:00:00Z','1'*64)['offers'][0]
 def test_units(self):
  o=self.ha();self.assertEqual(o['allocation_hour_usd'],2.99);self.assertEqual(o['minimum_charge_s'],3600)
 def test_missing_is_unknown(self):
  o=self.ha(MinimumReservationMinutes=None,Quantity=None);self.assertIsNone(o['minimum_charge_s']);self.assertEqual(o['availability'],'unknown')
 def test_zero_stock(self): self.assertEqual(self.ha(Quantity=0)['availability'],'unavailable')
 def test_bad_price_not_free(self): self.assertIsNone(self.ha(OnDemandPrice=-1)['allocation_hour_usd'])
 def test_count_not_coerced(self):
  with self.assertRaises(ValueError): self.ha(Specs={'gpus':[{'count':True}]})
 def test_runpod_context(self):
  o=m.normalize_runpod({'gpus':[{'id':'demo','price':{'secure':2,'community':1},'availability':'HIGH'}]},'2026-09-24T19:00:00Z','1'*64,4,'SECURE')['offers'][0]
  self.assertEqual(o['allocation_hour_usd'],8);self.assertEqual(o['availability'],'listed');self.assertIsNone(o['minimum_charge_s']);self.assertEqual(o['product'],'POD')
 def test_credential_fields_omitted(self):
  o=self.ha(Secret='DO_NOT_EXPORT',Team='CUSTOMER_NAME');self.assertNotIn('DO_NOT_EXPORT',json.dumps(o));self.assertNotIn('CUSTOMER_NAME',json.dumps(o))
 def test_release_not_runtime_approval(self):
  o=m.summarize('release',{'tag_name':'v1','body':'untrusted install script'});self.assertNotIn('body',o);self.assertIn('not installation',o['interpretation'])
 def test_redirect_refused(self):
  with self.assertRaises(ValueError):m.NoRedirect().redirect_request(None,None,302,'',None,'https://other.invalid')
 def test_error_does_not_print_token_or_url(self):
  self.assertEqual(m.safe_error(ValueError('token-secret')),'UNREADABLE_OR_INVALID_SOURCE')
if __name__=='__main__':unittest.main()
