"""Decision Floor standalone local evaluation console. CPython 3.10+, stdlib only.

Security boundary: binds 127.0.0.1 only, random per-session header token,
no outbound network, no customer data outside the specified project directory.
Local host users/browser extensions are NOT considered adversaries here.
"""
import argparse
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sys
import tempfile
from threading import RLock
from urllib.parse import parse_qs,urlsplit

from decision_floor.cli import execute
from decision_floor.core import make_db, search, verify, load_rules, rows, SUPPORTED, iso_now

ROOT = Path(__file__).resolve().parent
MAX_POST = 12_000_000
MAX_UPLOAD = 8_000_000
FILE_PATTERN = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\Z')
HEX_PATTERN = re.compile(r'[0-9a-f]{64}\Z')
SAFE_EXPORTS = {'decision_floor_report.json','investigation_history.json',
                'open_questions.json','verification.json'}


def prepare_project(project):
    root=Path(project).expanduser().resolve()
    if root == ROOT:
        raise ValueError('Customer workspace cannot replace the product installation')
    if ROOT in root.parents and root.relative_to(ROOT).parts[0] not in ('local_customer','local_demo'):
        raise ValueError('Within the installation, only local_customer/ and local_demo/ are workspace roots')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ('incoming','state','report','config'):
        (root/name).mkdir(exist_ok=True,mode=0o700)
    config=root/'config'/'sources.json'
    if not config.exists():
        shutil.copy2(ROOT/'config'/'sources.json',config)
    load_rules(config)
    return root


def safe_mapping(cfg):
    if not isinstance(cfg,dict) or not isinstance(cfg.get('sources'),list):
        raise ValueError('Mapping must contain sources array')
    if len(cfg['sources'])>150:raise ValueError('Too many source mappings')
    # Keep all glob matching within intake; no traversals, no subdirectory escape.
    for r in cfg['sources']:
        if not isinstance(r,dict):raise ValueError('Invalid mapping')
        patt=r.get('pattern','')
        if not isinstance(patt,str) or len(patt)>130 or not FILE_PATTERN.fullmatch(patt.replace('*','A').replace('?','Q')) or '/' in patt or '\\' in patt or '..' in patt:
            raise ValueError('Source patterns must be simple relative basenames')
        if not isinstance(r.get('fields'),dict):raise ValueError('Source mapping requires fields')
        if any(not isinstance(v,str) or len(v)>150 for v in r['fields'].values()):
            raise ValueError('Source column names must be strings')
        if len(str(r.get('system','')))>180:raise ValueError('Source system label too long')
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)/'mapping.json';p.write_text(json.dumps(cfg),encoding='utf8');load_rules(p)
    return cfg


def write_atomic(p,data):
    p.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.new-',dir=p.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,p)
        try:os.chmod(p,0o600)
        except OSError:pass
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def scan(project):
    args=argparse.Namespace(input=str(project/'incoming'),
                            config=str(project/'config'/'sources.json'),
                            workspace=str(project/'state'),
                            out=str(project/'report'),as_of=None)
    return execute(args)


def get_summary(project):
    fn=project/'report'/'decision_floor_report.json'
    rep=json.loads(fn.read_text(encoding='utf8')) if fn.exists() else {'cases':[],'event_count':0,'source_count':0,'issues':[],'skipped_files':[]}
    hist=project/'report'/'investigation_history.json'
    history=json.loads(hist.read_text(encoding='utf8')) if hist.exists() else {'items':[], 'transitions':[]}
    return {'cases':rep.get('cases',[]),'event_count':rep.get('event_count',0),
            'source_count':rep.get('source_count',0), 'issues':rep.get('issues',[]),
            'skipped_files':rep.get('skipped_files',[]),'as_of':rep.get('as_of'),
            'questions':[{'case_key':c['case_key'],**q} for c in rep.get('cases',[]) for q in c.get('questions',[])],
            'history':history,
            'files_waiting':sum(1 for p in (project/'incoming').iterdir() if p.is_file()),
            'last_run':rep.get('last_run')}


def make_handler(project,token,lock):
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'
        server_version='DecisionFloorLocal/0.2'
        sys_version=''
        def log_message(self,format,*args):
            # Do not log URL bearer tokens or source record content.
            print('local http '+str(self.command or '?')+' '+str(getattr(self,'path','')).split('?')[0]+' '+str(args[1] if len(args)>1 else ''),file=sys.stderr)
        def send_data(self,data,content_type='application/json; charset=utf-8',status=200,filename=None):
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('X-Frame-Options','SAMEORIGIN')
            self.send_header('Cross-Origin-Resource-Policy','same-origin')
            self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; base-uri 'none'; form-action 'none'")
            if filename:self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(data)
        def as_json(self,obj,status=200):
            self.send_data(json.dumps(obj,ensure_ascii=False,default=str).encode(),status=status)
        def authorized(self,query=None):
            header=self.headers.get('X-Local-Token','')
            if header == token:return True
            # Only bootstrap and report may use a query token for direct navigation.
            if query is not None and query.get('token',[''])[0]==token:return True
            self.as_json({'error':'Local bearer token required'},403)
            return False
        def do_GET(self):
            parts=urlsplit(self.path);query=parse_qs(parts.query)
            path=parts.path
            if path=='/':
                if not self.authorized(query):return
                s=(ROOT/'ui'/'index.html').read_text(encoding='utf8')
                s=s.replace('__TOKEN_JSON__',json.dumps(token)).replace('__TOKEN__',token)
                return self.send_data(s.encode(),'text/html; charset=utf-8')
            if path in ('/app.js','/style.css'):
                if not self.authorized(query):return
                name='app.js' if path=='/app.js' else 'style.css'
                mime='text/javascript; charset=utf-8' if path=='/app.js' else 'text/css; charset=utf-8'
                return self.send_data((ROOT/'ui'/name).read_bytes(),mime)
            if path=='/report':
                if not self.authorized(query):return
                p=project/'report'/'index.html'
                if not p.is_file():return self.as_json({'error':'Scan first'},404)
                return self.send_data(p.read_bytes(),'text/html; charset=utf-8')
            if not self.authorized():return
            try:
                if path=='/api/summary':return self.as_json(get_summary(project))
                if path=='/api/config':return self.as_json(json.loads((project/'config'/'sources.json').read_text()))
                if path=='/api/search':
                    needle=query.get('q',[''])[0][:140]
                    with lock:
                        db=make_db(project/'state')
                        try:result=search(db,needle,min(70,max(1,int(query.get('limit',['25'])[0]))))
                        finally:db.close()
                    return self.as_json({'query':needle,'hits':result})
                if path=='/api/reviews':
                    p=project/'state'/'reviews.jsonl'
                    return self.as_json({'reviews':[json.loads(line) for line in p.read_text(encoding='utf8').splitlines()] if p.exists() else []})
                if path=='/api/verify':
                    with lock:
                        db=make_db(project/'state')
                        try:v=verify(db,project/'state')
                        finally:db.close()
                    return self.as_json(v)
                if path=='/api/export':
                    name=query.get('name',[''])[0]
                    if name not in SAFE_EXPORTS:return self.as_json({'error':'Not an authorized export'},400)
                    p=project/'report'/name
                    if not p.is_file():return self.as_json({'error':'Report not found'},404)
                    return self.send_data(p.read_bytes(),'application/json; charset=utf-8',filename=name)
                if path=='/api/source':
                    sh=query.get('sha256',[''])[0]
                    if not HEX_PATTERN.fullmatch(sh):return self.as_json({'error':'Invalid source hash'},400)
                    with lock:
                        db=make_db(project/'state')
                        try:row=db.execute('SELECT original_name FROM sources WHERE digest=?',(sh,)).fetchone()
                        finally:db.close()
                    if not row:return self.as_json({'error':'Unknown source'},404)
                    p=project/'state'/'vault'/'objects'/sh
                    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=sh:
                        return self.as_json({'error':'Archived bytes missing or changed'},409)
                    suffix=Path(row['original_name']).suffix.lower()
                    return self.send_data(p.read_bytes(),'application/octet-stream',filename='source-'+sh[:12]+suffix)
                return self.as_json({'error':'Unknown path'},404)
            except Exception as exc:
                return self.as_json({'error':str(exc)},400)
        def do_POST(self):
            if not self.authorized():return
            parts=urlsplit(self.path)
            origin=self.headers.get('Origin','')
            if origin and origin!=f'http://127.0.0.1:{self.server.server_port}':
                return self.as_json({'error':'Origin mismatch'},403)
            try:
                size=int(self.headers.get('Content-Length','-1'))
            except ValueError:size=-1
            if size<0 or size>MAX_POST:return self.as_json({'error':'Request exceeds local limit'},413)
            try:
                body=json.loads(self.rfile.read(size))
                if not isinstance(body,dict):raise ValueError('JSON object required')
                path=parts.path
                if path=='/api/scan':
                    with lock:r=scan(project)
                    return self.as_json(r)
                if path=='/api/upload':
                    name=body.get('filename','')
                    if not isinstance(name,str) or not FILE_PATTERN.fullmatch(name) or '..' in name or Path(name).suffix.lower() not in SUPPORTED:
                        raise ValueError('Only supported, simple filenames are allowed')
                    encoded=body.get('bytes_base64','')
                    if not isinstance(encoded,str) or len(encoded)>MAX_UPLOAD*4//3+10:raise ValueError('Upload exceeds limit')
                    raw=base64.b64decode(encoded,validate=True)
                    if len(raw)>MAX_UPLOAD:raise ValueError('File exceeds 8MB browser upload limit; use customer-owned drop folder instead')
                    dst=project/'incoming'/name
                    with lock:
                        # Archive the original first so a changed filename never loses the earlier version.
                        if dst.exists() and hashlib.sha256(dst.read_bytes()).digest()!=hashlib.sha256(raw).digest():scan(project)
                        write_atomic(dst,raw)
                    return self.as_json({'stored':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
                if path=='/api/config':
                    cfg=safe_mapping(body.get('mapping'))
                    with lock:
                        write_atomic(project/'config'/'sources.json',(json.dumps(cfg,indent=2)+'\n').encode())
                    return self.as_json({'stored':'config/sources.json','rules':len(cfg['sources'])})
                if path=='/api/review':
                    actor=str(body.get('actor','')).strip()[:120]
                    case=str(body.get('case_key','')).strip()[:200]
                    code=str(body.get('code','')).strip()[:160]
                    note=str(body.get('note','')).strip()[:2000]
                    disposition=str(body.get('disposition','')).strip()
                    if not (case and code and actor and note) or disposition not in ('evidence_requested','acknowledged','reviewed'):
                        raise ValueError('Review requires case, finding code, reviewer, disposition and justification')
                    with lock:
                        summary=get_summary(project)
                        if (case,code) not in {(q['case_key'],q['code']) for q in summary['questions']}:
                            raise ValueError('Finding is not present in current evidence projection')
                        entry={'at':iso_now(),'case_key':case,'code':code,'actor':actor,
                               'disposition':disposition,'note':note}
                        entry['sha256']=hashlib.sha256(json.dumps(entry,sort_keys=True).encode()).hexdigest()
                        fn=project/'state'/'reviews.jsonl'
                        with fn.open('a',encoding='utf8') as f:f.write(json.dumps(entry,ensure_ascii=False)+'\n')
                    return self.as_json(entry)
                return self.as_json({'error':'Unknown action'},404)
            except Exception as exc:
                return self.as_json({'error':str(exc)},400)
    return Handler


def serve(project,port=0):
    root=prepare_project(project)
    token=secrets.token_urlsafe(32)
    lock=RLock()
    handler=make_handler(root,token,lock)
    with ThreadingHTTPServer(('127.0.0.1',int(port)),handler) as server:
        url=f'http://127.0.0.1:{server.server_port}/?token={token}'
        print('\nDecision Floor | Independent offline evaluation',flush=True)
        print('Open this local URL on the same computer:\n'+url,flush=True)
        print('Workspace: '+str(root),flush=True)
        print('This service is loopback-only. Ctrl+C to stop.\n',flush=True)
        try:server.serve_forever(poll_interval=0.25)
        except KeyboardInterrupt:pass


def main():
    p=argparse.ArgumentParser(description='Decision Floor offline investigator with an optional local console')
    sub=p.add_subparsers(dest='action',required=True)
    s=sub.add_parser('serve',help='Launch authorized localhost-only UI')
    s.add_argument('--project',default='local_customer');s.add_argument('--port',type=int,default=0)
    s=sub.add_parser('scan',help='Scan local project exports and regenerate report')
    s.add_argument('--project',default='local_customer')
    a=p.parse_args()
    if a.action=='serve':serve(a.project,a.port)
    else:print(json.dumps(scan(prepare_project(a.project)),indent=2))

if __name__=='__main__':main()
