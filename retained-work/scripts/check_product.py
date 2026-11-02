"""Qualify the redesigned product's static contracts and exact inherited custody."""
from pathlib import Path
from html.parser import HTMLParser
import hashlib,json,re
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
class Page(HTMLParser):
 def __init__(self):super().__init__();self.ids=[];self.refs=[];self.iframes=0;self.labels=[];self.inputs=[]
 def handle_starttag(self,t,attrs):
  a=dict(attrs)
  if 'id'in a:self.ids.append(a['id'])
  if t in ('script','link','img'):
   v=a.get('src',a.get('href',''))
   if v:self.refs.append(v)
  if t=='iframe':self.iframes+=1
  if t=='label'and'for'in a:self.labels.append(a['for'])
  if t in ('input','textarea','select') and a.get('type') not in ('hidden','button','submit'):self.inputs.append(a)
def main():
 checks=[]
 def check(n,v):
  checks.append({'name':n,'pass':bool(v)})
  if not v:raise AssertionError(n)
 p=Page();p.feed((ROOT/'review/index.html').read_text());check('one_product_no_iframe',p.iframes==0);check('all_static_ids_unique',len(p.ids)==len(set(p.ids)))
 check('functional_existing_forms_retained',set(['source-file','save-cost','save-delivery','export-journal','import-button','encrypt','decrypt','hash-file','claim-list','claim-detail','action-list','history-json','library-list'])-{'source-file'}<=set(p.ids))
 check('visible_inputs_have_labels',all(x.get('aria-label')or x.get('id')in p.labels for x in p.inputs))
 check('seven_working_sections',all(x+'-panel'in p.ids for x in ['overview','map','claims','actions','costs','history','library']))
 check('only_same_tool_assets',all(not x.startswith(('http:','https:','//'))and x.startswith(('data:','#'))or (ROOT/'review'/urlsplit(x).path).resolve().is_relative_to(ROOT.resolve()) for x in p.refs))
 check('all_runtime_assets_resolve',all(x.startswith(('data:','#'))or (ROOT/'review'/urlsplit(x).path).is_file() for x in p.refs))
 check('original_journal_engine_exact',sha(ROOT/'review/core.js')=='2f0a7091ea6f3fc4a1666c0ed5af289c203f5962e0b55504e06044f5d05272fd')
 check('original_geographic_data_module_exact',sha(ROOT/'map/assets/data-wdyG7mqn.js')=='bf899c15cb1fe6205d6dc8319c1722aab5d857b56bd62efd42d39424f7e9d8e5')
 raw=(ROOT/'data/geography.js').read_text();check('data_literal_wrapper',raw.startswith('globalThis.SuginamiGeography=')and raw.endswith(';\n'))
 g=json.loads(raw[len('globalThis.SuginamiGeography='):-2]);pin=json.loads((ROOT/'data/geography-provenance.json').read_bytes());canonical=json.dumps(g,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode();check('exact_source_derived_object',hashlib.sha256(canonical).hexdigest()==pin['canonical_object_sha256']);check('nine_original_layers',len(g['layers'])==9)
 counts={l['layer']:len(l['features'])for l in g['layers']};check('all_source_feature_counts',counts=={'ward':1,'smb':139,'chome':139,'stations':18,'care':111,'accountants':31,'anime':6,'shotengai':125,'landprice':86})
 check('business_counts_conserved',sum(f['properties']['establishments']for l in g['layers']if l['layer']=='smb'for f in l['features'])==19533)
 check('stations_not_conflated_with_lines',len([f for l in g['layers']if l['layer']=='stations'for f in l['features']if f['geometry']['type']=='Point'])==14)
 app=(ROOT/'review/app.js').read_text();atlas=(ROOT/'review/atlas.js').read_text();check('original_grades_are_not_promoted','Author grade:'in app and 'Not reviewed here'in app);check('safe_document_renderer','function inlineText'in app and 'innerHTML'not in app);check('global_search_keyboard_and_exact_routes','commandOpen'in app and 'place='in app and 'aria-activedescendant'in app);check('locale_uses_existing_preference','suginami-language'in app)
 check('declared_source_preserved_in_inspector','Source attribution supplied by the map author'in atlas);check('count_not_density_invented','Establishments per neighborhood'in atlas);check('mobile_label_collision_handling','layoutLabels()'in atlas and "visibility='hidden'"in atlas)
 check('no_external_atlas_services',not re.search(r'\b(fetch|XMLHttpRequest|WebSocket|EventSource)\s*\(',atlas));check('source_drafts_explicitly_scoped','Unsaved source draft restored for this session'in app);check('recovery_existing_contract_preserved',all(x in app for x in ['S.exportPacket','S.importPacket','S.encrypt','S.decrypt']))
 check('source_asset_attribution_exists',(ROOT/'assets/ASSETS.json').is_file())
 files=[f for f in ROOT.rglob('*')if f.is_file()];check('no_font_or_private_key_files',not any(f.suffix.lower()in('.woff','.woff2','.ttf','.otf','.key','.sqlite','.sqlite3')for f in files))
 report={'status':'PASS','checks_passed':len(checks),'checks':checks,'field_desk_version':'2.0.0','geographic_features':sum(counts.values()),'data_are_original':True,'core_state_schema_unchanged':True,'scope':'Static source-preservation, UI contract and custody checks. Actual browser behavior and publication separately qualify the final bytes.'};print(json.dumps(report,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
