from pathlib import Path
import json,hashlib,re,sys
root=Path(__file__).resolve().parents[1]
c=json.loads((root/'data/catalog.json').read_text(encoding='utf-8'))
assert len({x['id'] for x in c})==len(c)
for x in c:
 p=(root/x['path']).resolve();assert root in p.parents and p.is_file(),x['id']
 assert p.stat().st_size==x['bytes'],x['id']
 assert hashlib.sha256(p.read_bytes()).hexdigest()==x['sha256'],x['id']
 if x.get('text_path'):assert (root/x['text_path']).is_file()
for p in root.glob('*.html'):
 t=p.read_text(encoding='utf-8')
 for u in re.findall(r'(?:href|src)="([^"]+)"',t):
  if u.startswith(('https:','http:','#','mailto:')):continue
  assert (root/u.split('#')[0]).is_file(),u
for p in [*root.glob('*.html'),*root.glob('*.js'),*root.glob('data/*.json'),*root.glob('transcripts/*.txt')]:
 t=p.read_text(encoding='utf-8').lower()
 for blocked in ['sdmntpr','sig=','attachment_id','139 diamond','213 926 0865','malisaluong','c:\\users\\']:
  assert blocked not in t,(str(p),blocked)
print(json.dumps({'status':'PASS','source_occurrences':len(c),'distinct_source_files':len({x['path'] for x in c}),'sha256_checks':len(c),'local_links':'PASS','private-data-pattern-check':'PASS'}))
