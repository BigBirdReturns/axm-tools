"""Static/custody checks for the self-contained public brief. No network or source execution."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import hashlib,json,re,sys
ROOT=Path(__file__).resolve().parents[1]
class Page(HTMLParser):
 def __init__(self):super().__init__();self.ids=[];self.links=[];self.external=[];self.langs={'en':0,'ja':0};self.h1=0;self.scripts=[];self.script=False
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if 'id' in a:self.ids.append(a['id'])
  if tag=='h1':self.h1+=1
  if a.get('data-lang') in self.langs:self.langs[a['data-lang']]+=1
  if tag=='a' and 'href' in a:self.links.append(a['href'])
  if tag in ('script','img','iframe','link'):
   u=a.get('src',a.get('href',''))
   if u.startswith(('http:','https:','//')):self.external.append(u)
  if tag=='script':self.script=True
 def handle_endtag(self,tag):
  if tag=='script':self.script=False
 def handle_data(self,data):
  if self.script:self.scripts.append(data)
def main():
 checks=[]
 def test(name,condition):
  checks.append({'name':name,'pass':bool(condition)})
  if not condition:raise AssertionError(name)
 text=(ROOT/'index.html').read_text(encoding='utf-8');p=Page();p.feed(text)
 test('one_title_hierarchy',p.h1==1);test('unique_ids',len(p.ids)==len(set(p.ids)));test('complete_bilingual_pairs',p.langs['en']==p.langs['ja'] and p.langs['en']>100);test('no_remote_runtime_or_font',not p.external)
 test('seven_overlap_choices',len(re.findall(r'<button data-region=',text))==7);test('six_explicitly_illustrative_states',len(re.findall(r'<button data-scenario=',text))==6 and 'illustrative:true' in text)
 test('twelve_cost_categories_explicit',len(re.findall(r'data-cost="(?:base|reuse)"',text))==12)
 test('receiving_and_commercial_boundaries','external_customer_acceptance:false' in text and 'customer_revenue' in text and 'human_workflow_savings' in text)
 test('no_automatic_network_in_page',not re.search(r'\b(?:fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon)\s*\(',''.join(p.scripts)))
 broken=[]
 for u in p.links:
  split=urlsplit(u)
  if split.scheme or u.startswith('//'):continue
  if not split.path:
   if split.fragment and unquote(split.fragment) not in p.ids:broken.append(u)
   continue
  f=(ROOT/unquote(split.path)).resolve()
  if not f.exists():broken.append(u)
 test('all_relative_targets_exist',not broken)
 e=json.loads((ROOT/'data/evidence.json').read_bytes());by={x['id']:x for x in e['evidence']}
 test('operator_denominator_preserved',by['operator']['checks_passed']==35 and len(by['operator']['checks'])==35)
 test('browser_denominator_preserved',by['browser']['checks_passed']==54)
 test('observer_denominator_preserved',len(by['observer']['checks'])==5)
 test('two_host_scope_preserved',by['physical-exchange']['physical_hosts_tested']==2 and by['physical-exchange']['external_participants']==0)
 test('installed_source_identity_preserved',by['installation']['manifest_entries_verified']==119 and by['release']['source_commit']=='fc6478e2512ad4c4285114e848beb4436aa5afa2')
 o=json.loads((ROOT/'data/operations.json').read_bytes());test('floor_denominators_reconcile',o['assertions_hash_linked']+o['assertions_without_verified_link']==o['assertions_declared_accepted']==160 and o['regression']['skipped_within_total']==4)
 m=json.loads((ROOT/'data/finite-model.json').read_bytes());test('finite_proof_scope_preserved',len(m['native_checks'])==9 and m['portable_test_count_reported_by_handoff']==68 and 'compact closure' in m['not_established'])
 test('proposed_amounts_present',all(t in text for t in ['$35,000','$17,500','$15,000','$7,500']))
 forbidden=[r'C:\\Users\\',r'/mnt/w03data/',r'S:/Scratch/',r'/home/jonathan/',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'F8N-[A-Z0-9]{4}-',r'gh[pousr]_[A-Za-z0-9]{20,}']
 leak=[]
 for f in ROOT.rglob('*'):
  if not f.is_file() or f==Path(__file__).resolve():continue
  if f.suffix in ('.woff','.woff2','.ttf','.otf','.key','.sqlite','.sqlite3'):leak.append(f.name)
  if f.suffix in ('.html','.json','.md','.js','.txt'):
   t=f.read_text(encoding='utf-8')
   if any(re.search(pattern,t) for pattern in forbidden):leak.append(f.relative_to(ROOT).as_posix())
 test('public_custody_scan',not leak)
 test('working_translation_disclosed','working translation' in text and 'legal translation' in text)
 report={'status':'PASS','checks_passed':len(checks),'checks':checks,'page_sha256':hashlib.sha256((ROOT/'index.html').read_bytes()).hexdigest(),'language_pairs':p.langs['en'],'local_links':len([u for u in p.links if not urlsplit(u).scheme]),'external_runtime_requests':0,'scope':'Static public-page source and selective-custody checks, not domain application acceptance'}
 print(json.dumps(report,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
