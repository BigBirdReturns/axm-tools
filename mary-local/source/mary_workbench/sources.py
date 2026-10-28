"""Source lifecycle and disposable retrieval index over Genesis-owned evidence."""
from __future__ import annotations
import json,os,re,shutil,sqlite3,stat,tempfile,uuid
from contextlib import closing
from pathlib import Path
from typing import Any
from . import axm
from .common import BoundaryError,Cancelled,atomic_json,canonical,check_cancel,contained,hash_file,init_home,local_path,lock,now,private_dir,read_json,reparse,sha,validate_id
from .process import run_worker

FORMATS={'.md','.txt','.text','.json','.csv','.xlsx','.pdf','.docx','.html','.htm'}
EXCLUDED={'.git','.ssh','.aws','.azure','.gnupg','node_modules','.venv','venv','__pycache__','appdata','.cache'}
SECRETS=re.compile(r'^(\.env.*|id_rsa.*|id_ed25519.*|credentials(?:\..*)?|cookies(?:\..*)?|login data|.*\.(?:key|pem|pfx|p12))$',re.I)
STOP={'a','an','and','the','of','in','is','was','are','what','which','how','to','for','this','that','my','your','does','do','on','with','from','please','me','tell','about'}

class Sources:
    def __init__(self,root:Path):
        self.root=local_path(root);self.config=init_home(self.root);axm.initialize_keys(self.root)
        with self.db() as c:
            c.executescript('''PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,source_key TEXT UNIQUE NOT NULL,name TEXT NOT NULL,format TEXT NOT NULL,status TEXT NOT NULL,current_shard TEXT,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS versions(source_id TEXT NOT NULL,shard TEXT PRIMARY KEY,original_sha TEXT NOT NULL,source_bytes INTEGER NOT NULL,stored_bytes INTEGER NOT NULL,created_at TEXT NOT NULL,coverage TEXT NOT NULL,FOREIGN KEY(source_id) REFERENCES sources(id));
CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY,source_id TEXT NOT NULL,shard TEXT NOT NULL,span_id TEXT NOT NULL,text_sha TEXT NOT NULL,locator TEXT NOT NULL,UNIQUE(shard,span_id));
CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(text,content='');
CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
INSERT OR IGNORE INTO metadata VALUES('schema','mary/source-catalog@1');''')
            if c.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()[0]!='mary/source-catalog@1':raise BoundaryError('Unsupported catalog generation.')
    def db(self):
        c=sqlite3.connect(self.root/'sources.sqlite',timeout=30);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA synchronous=FULL');return c
    def list(self)->list[dict]:
        with closing(self.db()) as c:
            return [dict(r) for r in c.execute('SELECT s.id,s.name,s.format,s.status,s.updated_at,s.current_shard,count(v.shard) AS versions FROM sources s LEFT JOIN versions v ON v.source_id=s.id GROUP BY s.id ORDER BY s.name')]
    def source(self,source_id:str,*,history:bool=False)->dict:
        validate_id(source_id)
        with closing(self.db()) as c:r=c.execute('SELECT * FROM sources WHERE id=?',(source_id,)).fetchone()
        if r is None:raise BoundaryError('Unknown source.')
        if not history and r['status']!='current':raise BoundaryError('Source is withdrawn or inaccessible; select history explicitly.')
        if sha(r['source_key'].encode())[:24]!=r['id']:raise BoundaryError('Source identity mapping failed.')
        return dict(r)
    def original(self,source_id:str)->Path:
        r=self.source(source_id);meta,_=axm.verified_document(self.root,r['current_shard'])
        p=contained(self.root/'shards'/r['current_shard']/'content',meta['original_file'])
        if hash_file(p)!=meta['original_sha256']:raise BoundaryError('Original-file binding failed.')
        return p
    def admit(self,path:Path,*,source_key:str|None=None,cancel:Any=None)->dict:
        path=local_path(path,exists=True);axm.preflight_source(path,self.config['max_source_bytes'])
        if path.suffix.lower() not in FORMATS or SECRETS.fullmatch(path.name):raise BoundaryError('This file needs a permitted format/source adapter.')
        key=source_key or str(path);source_id=sha(key.encode())[:24];initial=path.stat();staging=private_dir(self.root/'runtime'/('source-'+uuid.uuid4().hex));snapshot=staging/path.name
        try:
            check_cancel(cancel)
            flags=os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0)
            with os.fdopen(os.open(path,flags),'rb') as src,snapshot.open('xb') as out:
                opened=os.fstat(src.fileno())
                if (opened.st_dev,opened.st_ino)!=(initial.st_dev,initial.st_ino):raise BoundaryError('Source identity changed before reading.')
                total=0
                while True:
                    check_cancel(cancel);data=src.read(1024*1024)
                    if not data:break
                    total+=len(data)
                    if total>self.config['max_source_bytes']:raise BoundaryError('Source grew beyond its file bound.')
                    out.write(data)
                after=os.fstat(src.fileno());out.flush();os.fsync(out.fileno())
            current=path.stat()
            expected=(initial.st_dev,initial.st_ino,initial.st_size,initial.st_mtime_ns)
            if any((s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)!=expected for s in (opened,after,current)) or reparse(path):raise BoundaryError('Source changed during capture; no new version admitted.')
            original_sha=hash_file(snapshot)
            with lock(self.root,'source-writer',timeout=30),closing(self.db()) as c:
                prior=c.execute('SELECT * FROM sources WHERE id=?',(source_id,)).fetchone()
                known=c.execute('SELECT * FROM versions WHERE source_id=? AND original_sha=? ORDER BY created_at DESC LIMIT 1',(source_id,original_sha)).fetchone()
                if known:
                    axm.verified_document(self.root,known['shard'])
                    c.execute('UPDATE sources SET current_shard=?,status=?,updated_at=? WHERE id=?',(known['shard'],'current',now(),source_id));c.commit()
                    return {'source_id':source_id,'shard_id':known['shard'],'status':'reused','coverage':known['coverage']}
                used=c.execute('SELECT COALESCE(sum(stored_bytes),0) FROM versions').fetchone()[0]
                if used+total>self.config['max_workspace_bytes']:raise BoundaryError('New content exceeds the workspace limit; unchanged sources remain reusable.')
                extraction=run_worker(self.root,'extract',{'path':str(snapshot)},seconds=90,cancel=cancel)
                check_cancel(cancel)
                sealed=axm.seal_document(self.root,snapshot,extraction,previous=prior['current_shard'] if prior else None)
                if used+sealed['bytes']>self.config['max_workspace_bytes']:raise BoundaryError('Sealed content exceeds storage policy; candidate retained for recovery, not activated.')
                meta,text=axm.verified_document(self.root,sealed['shard_id'])
                c.execute('BEGIN IMMEDIATE')
                try:
                    c.execute('INSERT INTO sources VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,format=excluded.format,status=excluded.status,current_shard=excluded.current_shard,updated_at=excluded.updated_at',(source_id,key,path.name,path.suffix.lower(),'current',sealed['shard_id'],now()))
                    c.execute('INSERT INTO versions VALUES(?,?,?,?,?,?,?)',(source_id,sealed['shard_id'],original_sha,total,sealed['bytes'],sealed['created_at'],sealed['coverage']))
                    for span in meta['spans']:
                        excerpt=text[span['byte_start']:span['byte_end']].decode('utf-8')
                        cur=c.execute('INSERT INTO chunks(source_id,shard,span_id,text_sha,locator) VALUES(?,?,?,?,?)',(source_id,sealed['shard_id'],span['id'],span['text_sha256'],canonical(span['locator']).decode()))
                        c.execute('INSERT INTO search(rowid,text) VALUES(?,?)',(cur.lastrowid,excerpt))
                    c.commit()
                except BaseException:c.rollback();raise
                return {'source_id':source_id,'status':'admitted',**sealed}
        finally:shutil.rmtree(staging,ignore_errors=True)
    def withdraw(self,source_id:str)->dict:
        self.source(source_id,history=True)
        with lock(self.root,'source-writer',timeout=30),closing(self.db()) as c:
            c.execute('UPDATE sources SET status=?,updated_at=? WHERE id=?',('withdrawn',now(),source_id));c.commit()
        return {'source_id':source_id,'status':'withdrawn','originals':'retained; excluded from default retrieval'}
    def begin_import(self,path:Path,request_id:str)->dict:
        validate_id(request_id);path=local_path(path,exists=True)
        if not path.is_dir() or path==Path(path.anchor) or path==Path.home().resolve() or path.is_relative_to(self.root) or self.root.is_relative_to(path):raise BoundaryError('Choose a specific source folder separate from the workspace.')
        record=self.root/'imports'/(request_id+'.json')
        with lock(self.root,'import-'+request_id):
            previous=read_json(record)
            if previous:
                if previous['root']!=str(path):raise BoundaryError('Request ID already names different source input.')
                return previous
            item={'id':request_id,'root':str(path),'status':'ready','directories':['.'],'pending':[],'seen':[],'processed':0,'admitted':0,'reused':0,'skipped':0,'errors':[],'created_at':now()}
            atomic_json(record,item);return item
    def import_batch(self,request_id:str,*,max_files:int|None=None,cancel:Any=None)->dict:
        validate_id(request_id);record=self.root/'imports'/(request_id+'.json')
        with lock(self.root,'import-'+request_id):
            item=read_json(record)
            if item is None:raise BoundaryError('Import identity not found.')
            if item['status']=='complete':return item
            source=local_path(Path(item['root']),exists=True);limit=max_files or self.config['max_import_files'];count=0;total=0;directories=0
            item['status']='running';atomic_json(record,item)
            try:
                while count<limit and total<self.config['max_import_bytes']:
                    check_cancel(cancel)
                    if not item['pending']:
                        if not item['directories']:break
                        if directories>=512:break
                        relative=item['directories'][0];directory=source if relative=='.' else contained(source,relative)
                        try:
                            if reparse(directory):raise BoundaryError('Source directory changed to a link.')
                            with os.scandir(directory) as iterator:
                                entries=[]
                                for entry in iterator:
                                    if len(entries)>=50000:raise BoundaryError('One directory exceeds 50,000 entries; use a narrower source root.')
                                    entries.append(entry)
                            for entry in sorted(entries,key=lambda e:e.name):
                                if entry.name.lower() in EXCLUDED or SECRETS.fullmatch(entry.name):item['skipped']+=1;continue
                                p=Path(entry.path)
                                if entry.is_symlink() or reparse(p):item['skipped']+=1;continue
                                rel=p.relative_to(source).as_posix()
                                if entry.is_dir(follow_symlinks=False):item['directories'].append(rel)
                                elif entry.is_file(follow_symlinks=False) and p.suffix.lower() in FORMATS:item['pending'].append(rel)
                                else:item['skipped']+=1
                        except (OSError,BoundaryError) as e:item['errors'].append({'path':relative,'error':str(e)})
                        item['directories'].pop(0);directories+=1;atomic_json(record,item);continue
                    relative=item['pending'][0];p=contained(source,relative)
                    try:
                        n=p.stat().st_size
                        if count and total+n>self.config['max_import_bytes']:break
                        result=self.admit(p,cancel=cancel);item['admitted' if result['status']=='admitted' else 'reused']+=1;item['seen'].append(result['source_id']);total+=n
                    except Cancelled:raise
                    except (OSError,BoundaryError) as e:item['errors'].append({'path':relative,'error':str(e)})
                    item['pending'].pop(0);item['processed']+=1;count+=1;atomic_json(record,item)
                item['status']='complete' if not item['directories'] and not item['pending'] else 'paused'
                item['coverage']='complete-supported-files' if item['status']=='complete' and not item['errors'] else 'partial'
                item['last_batch_files']=count;item['last_batch_bytes']=total;item['updated_at']=now();atomic_json(record,item)
                return item
            except BaseException:
                item['status']='paused';item['updated_at']=now();atomic_json(record,item);raise
    def search(self,question:str,*,source_ids:list[str]|None=None,limit:int=8,history:bool=False)->list[dict]:
        if not isinstance(question,str) or len(question)>8000 or not 1<=limit<=32:raise BoundaryError('Search input exceeds its bound.')
        words=list(dict.fromkeys(w.lower() for w in re.findall(r'\w+',question) if w.lower() not in STOP))[:24]
        if not words:return []
        query=' OR '.join('"'+w+'"' for w in words)
        params=[query];where=['search MATCH ?']
        if not history:where.append("s.status='current' AND s.current_shard=c.shard")
        if source_ids:
            for sid in source_ids:validate_id(sid)
            where.append('s.id IN ('+','.join('?' for _ in source_ids)+')');params.extend(source_ids)
        params.append(limit)
        with closing(self.db()) as c:
            rows=c.execute('SELECT c.*,s.name,s.source_key FROM search JOIN chunks c ON c.id=search.rowid JOIN sources s ON s.id=c.source_id WHERE '+' AND '.join(where)+' ORDER BY bm25(search) LIMIT ?',params).fetchall()
        if not rows:return []
        documents={};result=[]
        # Re-derive every evidence body from its verified sealed source. The index
        # contains only discovery hints; its text can never become answer evidence.
        for r in rows:
            if r['shard'] not in documents:documents[r['shard']]=axm.verified_document(self.root,r['shard'])
            meta,data=documents[r['shard']];span=next((x for x in meta['spans'] if x['id']==r['span_id']),None)
            if span is None or span['text_sha256']!=r['text_sha'] or canonical(span['locator']).decode()!=r['locator']:raise BoundaryError('Retrieval coordinates differ from sealed evidence. Rebuild the disposable index.')
            text=data[span['byte_start']:span['byte_end']].decode('utf-8')
            if sha(text.encode())!=r['text_sha']:raise BoundaryError('Retrieval source span integrity failed.')
            if sha(r['source_key'].encode())[:24]!=r['source_id']:raise BoundaryError('Source identity mapping failed.')
            result.append({'source_id':r['source_id'],'name':meta['name'],'shard_id':r['shard'],'span_id':span['id'],'byte_start':span['byte_start'],'byte_end':span['byte_end'],'locator':span['locator'],'text':text,'coverage':meta['coverage'],'history':history})
        # Exercise Core's native mounted evidence query, not a parallel shard schema.
        inspected=axm.spectra_claims(self.root,list(documents))
        if not inspected['rows']:raise BoundaryError('Spectra returned no mounted source claims.')
        return result
    def rebuild(self)->dict:
        with lock(self.root,'source-writer',timeout=30),closing(self.db()) as c:
            versions=c.execute('SELECT source_id,shard FROM versions').fetchall();items=[]
            for version in versions:
                meta,data=axm.verified_document(self.root,version['shard'])
                for span in meta['spans']:items.append((version['source_id'],version['shard'],span,data[span['byte_start']:span['byte_end']].decode()))
            c.execute('BEGIN IMMEDIATE')
            try:
                c.execute("INSERT INTO search(search) VALUES('delete-all')");c.execute('DELETE FROM chunks')
                for sid,shard,span,text in items:
                    cur=c.execute('INSERT INTO chunks(source_id,shard,span_id,text_sha,locator) VALUES(?,?,?,?,?)',(sid,shard,span['id'],span['text_sha256'],canonical(span['locator']).decode()));c.execute('INSERT INTO search(rowid,text) VALUES(?,?)',(cur.lastrowid,text))
                c.commit()
            except BaseException:c.rollback();raise
            return {'status':'accepted','shards':len(versions),'chunks':len(items)}
