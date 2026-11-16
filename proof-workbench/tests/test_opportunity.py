import importlib.util,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import opportunity as o
class OpportunityTests(unittest.TestCase):
 def journal(self):return {'schema':'axm-proof-opportunity/1','id':'TEST-001','disclosure':'private','events':[]}
 def event(self,kind,n=1,**extra):return {'id':str(n),'kind':kind,'at':f'2026-11-15T12:{n:02d}:00Z','source_ref':'synthetic:fixture:'+str(n),**extra}
 def test_auto_reply_no_progress(self):
  j=self.journal();j['events']=[self.event('sent'),self.event('auto_reply',2),self.event('attention_reported',3),self.event('intermediary_followup',4)];self.assertEqual(o.project(j)['state'],'sent')
 def test_visit_not_test(self):
  j=self.journal();j['events']=[self.event('courtesy_visit_offered')];self.assertEqual(o.project(j)['state'],'acknowledged')
 def test_acceptance_cannot_skip_test(self):
  j=self.journal();j['events']=[self.event('accepted',decision_owner='reviewer',disposition_ref='fixture')];self.assertRaises(ValueError,o.project,j)
 def test_agreed_test_requires_permissions(self):
  j=self.journal();j['events']=[self.event('reviewer_assigned',owner='reviewer'),self.event('test_agreed',2,acceptance_ref='fixture')];self.assertRaises(ValueError,o.project,j)
 def test_complete_declared_chain(self):
  j=self.journal();j['events']=[self.event('reviewer_assigned',owner='reviewer'),self.event('test_agreed',2,acceptance_ref='fixture',data_authorization_ref='fixture'),self.event('recipient_run',3,recipient='other',receipt_sha256='a'*64),self.event('accepted',4,decision_owner='reviewer',disposition_ref='fixture')];p=o.project(j);self.assertEqual(p['state'],'accepted');self.assertFalse(p['send_allowed'])
 def test_missing_evidence(self):
  j=self.journal();j['events']=[self.event('sent',source_ref='')];self.assertRaises(ValueError,o.project,j)
 def test_terminal_cannot_restart(self):
  j=self.journal();j['events']=[self.event('declined'),self.event('sent',2)];self.assertRaises(ValueError,o.project,j)
 def test_reordered_history(self):
  j=self.journal();j['events']=[self.event('sent',2),self.event('review_promised',1)];self.assertRaises(ValueError,o.project,j)
 def test_duplicate_event(self):
  j=self.journal();j['events']=[self.event('sent'),self.event('auto_reply')];self.assertRaises(ValueError,o.project,j)
 def test_private_boundary(self):
  j=self.journal();j['disclosure']='public';self.assertRaises(ValueError,o.project,j)
