#!/usr/bin/env python3
"""Evidence-referenced private engagement progression; no communication effects."""
import argparse,datetime as dt,json,re,sys
from pathlib import Path
from proof import Refusal,load,dump
LEVELS=['artifact_ready','sent','acknowledged','reviewer_assigned','test_agreed','recipient_tested','accepted']
TYPES={'artifact_published':'artifact_ready','sent':'sent','review_promised':'acknowledged','courtesy_visit_offered':'acknowledged','reviewer_assigned':'reviewer_assigned','test_agreed':'test_agreed','recipient_run':'recipient_tested','accepted':'accepted'}
NOTES={'auto_reply','intermediary_followup','attention_reported','scope_excluded','note'}
def project(j):
 if not isinstance(j,dict) or j.get('schema')!='axm-proof-opportunity/1' or j.get('disclosure')!='private' or not isinstance(j.get('events'),list):raise Refusal('OPPORTUNITY_SCHEMA')
 if not isinstance(j.get('id'),str) or not re.fullmatch('[A-Za-z0-9_-]{3,80}',j['id']):raise Refusal('OPPORTUNITY_ID')
 state='unobserved';previous=None;seen=set();trace=[];terminal=None
 for e in j['events']:
  if not isinstance(e,dict) or not isinstance(e.get('id'),str) or e['id'] in seen:raise Refusal('DUPLICATE_OR_MISSING_EVENT')
  seen.add(e['id']);kind=e.get('kind');ref=e.get('source_ref')
  if kind not in set(TYPES)|NOTES|{'declined','withdrawn'}:raise Refusal('UNKNOWN_EVENT')
  if not isinstance(ref,str) or not ref.strip():raise Refusal('SOURCE_REF_REQUIRED')
  stamp=dt.datetime.fromisoformat(e.get('at','').replace('Z','+00:00'))
  if stamp.tzinfo is None or (previous is not None and stamp<previous):raise Refusal('EVENT_TIME_ORDER')
  previous=stamp
  if terminal and kind not in NOTES:raise Refusal('TERMINAL_REQUIRES_NEW_OPPORTUNITY')
  if kind in ('declined','withdrawn'):terminal=kind
  if kind in TYPES:
   dest=TYPES[kind];level=LEVELS.index(dest);current=LEVELS.index(state) if state in LEVELS else -1
   if kind=='reviewer_assigned' and not e.get('owner'):raise Refusal('REVIEWER_OWNER_REQUIRED')
   if kind=='test_agreed':
    if current<3 or not e.get('acceptance_ref') or not e.get('data_authorization_ref'):raise Refusal('TEST_AGREEMENT_REQUIRED')
   if kind=='recipient_run':
    if current<4 or not e.get('recipient') or not re.fullmatch('[a-f0-9]{64}',str(e.get('receipt_sha256',''))):raise Refusal('RECIPIENT_EXECUTION_REQUIRED')
   if kind=='accepted':
    if current<5 or not e.get('decision_owner') or not e.get('disposition_ref'):raise Refusal('RECIPIENT_ACCEPTANCE_REQUIRED')
   if level>current:state=dest
  trace.append({'event':e['id'],'kind':kind,'at':e['at'],'source_ref':ref,'state':terminal or state})
 return {'schema':'axm-proof-opportunity-state/1','id':j['id'],'state':terminal or state,'last_progress':state,'events':len(seen),'trace':trace,'basis':'Structured references and declared observations; source authentication requires the referenced evidence. Replies, opens, visits and intermediary attention never imply technical acceptance.','send_allowed':False,'execute_allowed':False,'publish_allowed':False}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('journal',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
 try:
  result=project(load(a.journal))
  if a.output:
   if a.output.exists():raise Refusal('OUTPUT_EXISTS')
   dump(a.output,result)
  print(json.dumps(result,indent=2));return 0
 except (ValueError,TypeError,OSError,KeyError) as e:print(json.dumps({'status':'REFUSED','reason':str(e)}),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
