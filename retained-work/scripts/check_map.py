"""Public-map source/closure checks. The actual browser run is a separate receipt."""
from pathlib import Path
from html.parser import HTMLParser
import json,hashlib,re,zipfile
ROOT=Path(__file__).resolve().parents[1]
class Page(HTMLParser):
 def __init__(self):super().__init__();self.resources=[];self.ids=[]
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if 'id' in d:self.ids.append(d['id'])
  if tag in ('script','link','img','iframe'):
   u=d.get('src',d.get('href',''))
   if u:self.resources.append(u)
def main():
 checks=[]
 def check(n,v):
  checks.append({'name':n,'pass':bool(v)})
  if not v:raise AssertionError(n)
 d=json.loads((ROOT/'data/map-data.json').read_bytes());ids={r['factId'] for r in d['facts']};actions={r['id']:r for r in d['actions']}
 check('45_unique_original_claims',len(d['facts'])==len(ids)==45)
 check('15_original_relations',len(d['edges'])==15 and all(r['fromFactId'] in ids and r['toFactId'] in ids for r in d['edges']))
 check('ten_unique_original_actions',len(d['actions'])==len(actions)==10)
 check('all_original_action_references_resolve',all(all(x in actions for x in a['deps']) and all(x in ids for x in a['facts']) for a in actions.values()))
 done=set()
 def visit(n,chain):
  if n in chain:raise AssertionError('action_cycle')
  for x in actions[n]['deps']:visit(x,chain|{n})
  done.add(n)
 for n in actions:visit(n,set())
 check('original_action_graph_is_acyclic',len(done)==10)
 check('original_grades_retained',sum(r['evidenceGrade']=='verified' for r in d['facts'])==34)
 pin=json.loads((ROOT/'data/SOURCE_MAP.json').read_bytes())
 check('exact_original_archive_identity',pin['original_archive_sha256']=='88e7524c2a6dc831f3cb4c70d6f5220458dcc79edd68fdbdbd5e948c5d2e986f')
 for row in pin['files']:
  f=ROOT/'map'/row['file'];check('map_asset_'+f.name,hashlib.sha256(f.read_bytes()).hexdigest()==row['published_sha256'])
 check('geographic_data_bytes_unchanged',next(r for r in pin['files'] if 'data-wdy' in r['file'])['source_sha256']==next(r for r in pin['files'] if 'data-wdy' in r['file'])['published_sha256'])
 for rel in ['map/index.html','review/index.html']:
  f=ROOT/rel;p=Page();p.feed(f.read_text());check(rel+'_unique_ids',len(p.ids)==len(set(p.ids)))
  check(rel+'_same_tool_runtime_only',all(u.startswith('data:') or (not re.match(r'^(?:https?:)?//|^/',u) and (f.parent/u.split('?')[0]).resolve().is_relative_to(ROOT.resolve()) and (f.parent/u.split('?')[0]).exists()) for u in p.resources))
 bridge=(ROOT/'map/bridge.js').read_text();core=(ROOT/'review/core.js').read_text();app=(ROOT/'review/app.js').read_text()
 check('no_native_api_imitation','/api/' not in bridge and '/api/' not in core and '/api/' not in app)
 check('browser_state_durability_and_integrity','navigator.locks.request' in core and 'event_checksum' in core and 'source_checksum' in core and 'divergent_history_preserved' in core)
 check('encrypted_export_distinct_from_native','suginami/public-browser-encrypted@1' in core and 'contains_signing_keys:false' in core)
 check('all_inclusion_dispositions_exposed',len(json.loads((ROOT/'data/access-ledger.json').read_bytes())['items'])==13)
 check('direct_map_and_desk_on_front_door','href="review/"' in (ROOT/'index.html').read_text() and 'href="map/"' in (ROOT/'index.html').read_text())
 check('no_font_files_distributed',not any(f.suffix in ['.woff','.woff2','.ttf','.otf'] for f in ROOT.rglob('*')))
 check('no_font_face_requests','@font-face' not in (ROOT/'map/assets/index-Xv0lQ5x8.css').read_text())
 forbidden=[r'C:\\Users\\',r'/mnt/w03data/',r'/home/jonathan/',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'gh[pousr]_[A-Za-z0-9]{20,}']
 leaks=[]
 for f in ROOT.rglob('*'):
  if f.suffix in ('.html','.md','.js','.json') and f.is_file():
   text=f.read_text()
   if any(re.search(x,text) for x in forbidden):leaks.append(str(f.relative_to(ROOT)))
 check('public_private_data_scan',not leaks)
 report={'status':'PASS','checks_passed':len(checks),'checks':checks,'source_archive_sha256':pin['original_archive_sha256'],'scope':'Static source, data preservation and public access checks; browser execution separately qualified.'}
 print(json.dumps(report,ensure_ascii=False,indent=2));return report
if __name__=='__main__':main()
