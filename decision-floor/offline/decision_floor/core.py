"""Content-addressed local ingestion and evidence-backed operational reconciliation.

Only Python's standard library is required for CSV/JSON/JSONL/TXT/MD/EML/HTML/
DOCX/XLSX. Optional offline pypdf processes text PDFs, if already installed.
This package never opens network connections or invokes external processes.
"""
from __future__ import annotations
import csv
import datetime as dt
import email
from email import policy
import hashlib
import html
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
from typing import Any
import uuid
import zipfile
import xml.etree.ElementTree as ET

UTC = dt.timezone.utc
SUPPORTED = {'.csv','.json','.jsonl','.txt','.md','.log','.eml','.html','.htm','.docx','.xlsx','.pdf'}
VALID_KINDS = {'forecast','decision','promise','plan','commitment','floor','outcome','inventory_target','unit_cost','sales_actual'}
QUANTITY_KINDS = VALID_KINDS - {'promise'}


def iso_now() -> str:
    return dt.datetime.now(UTC).isoformat(timespec='seconds')


def parse_time(value: Any) -> str | None:
    if value is None or str(value).strip() == '':
        return None
    s=str(value).strip()
    try:
        v=dt.datetime.fromisoformat(s.replace('Z','+00:00'))
    except ValueError as exc:
        raise ValueError(f'Invalid ISO timestamp {s!r}: {exc}') from exc
    if v.tzinfo is None or v.utcoffset() is None:
        raise ValueError(f'Timestamp requires explicit timezone offset: {s}')
    return v.astimezone(UTC).isoformat(timespec='seconds')


def t(s: str | None) -> dt.datetime | None:
    return dt.datetime.fromisoformat(s) if s else None


def digest(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def json_text(x: Any) -> str:
    return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))


def make_db(workspace: Path) -> sqlite3.Connection:
    workspace.mkdir(parents=True,exist_ok=True,mode=0o700)
    vault=workspace/'vault'/'objects'; vault.mkdir(parents=True,exist_ok=True,mode=0o700)
    dbfile=workspace/'evidence.sqlite3'
    db=sqlite3.connect(dbfile)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
CREATE TABLE IF NOT EXISTS sources(
 digest TEXT PRIMARY KEY, byte_count INTEGER NOT NULL, original_name TEXT NOT NULL,
 first_ingested TEXT NOT NULL, ext TEXT NOT NULL, vault_relpath TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_paths(
 path TEXT NOT NULL, digest TEXT NOT NULL, last_seen TEXT NOT NULL,
 PRIMARY KEY(path,digest),FOREIGN KEY(digest) REFERENCES sources(digest));
CREATE TABLE IF NOT EXISTS fragments(
 id TEXT PRIMARY KEY, source_digest TEXT NOT NULL, locator TEXT NOT NULL,
 body TEXT NOT NULL, extractor TEXT NOT NULL,
 FOREIGN KEY(source_digest) REFERENCES sources(digest));
CREATE TABLE IF NOT EXISTS events(
 id TEXT PRIMARY KEY, source_digest TEXT NOT NULL, locator TEXT NOT NULL,
 case_id TEXT, kind TEXT NOT NULL, record_id TEXT NOT NULL, site TEXT NOT NULL,
 sku TEXT NOT NULL, period TEXT NOT NULL,
 occurred_at TEXT NOT NULL, recorded_at TEXT,
 system TEXT NOT NULL, authority TEXT, quantity REAL,
 track TEXT, decision_id TEXT, due_at TEXT, owner TEXT, status TEXT,
 notes TEXT, raw_json TEXT NOT NULL,
 FOREIGN KEY(source_digest) REFERENCES sources(digest));
CREATE INDEX IF NOT EXISTS ix_events_case ON events(site,sku,period,occurred_at);
CREATE INDEX IF NOT EXISTS ix_events_decision ON events(decision_id);
CREATE TABLE IF NOT EXISTS issues(
 id TEXT PRIMARY KEY, source_digest TEXT, locator TEXT,
 severity TEXT NOT NULL, code TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS issue_resolutions(
 issue_id TEXT PRIMARY KEY, resolved_at TEXT NOT NULL,
 FOREIGN KEY(issue_id) REFERENCES issues(id));
CREATE TABLE IF NOT EXISTS skipped_files(
 path TEXT PRIMARY KEY, reason TEXT NOT NULL, last_checked TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS investigation_items(
 id TEXT PRIMARY KEY, case_key TEXT NOT NULL, code TEXT NOT NULL, first_seen TEXT NOT NULL,
 last_seen TEXT NOT NULL, state TEXT NOT NULL, last_question TEXT NOT NULL, owner TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS investigation_transitions(
 id TEXT PRIMARY KEY, finding_id TEXT NOT NULL, happened_at TEXT NOT NULL,
 previous_state TEXT, next_state TEXT NOT NULL, reason TEXT NOT NULL,
 supporting_evidence_json TEXT NOT NULL,
 FOREIGN KEY(finding_id) REFERENCES investigation_items(id));
CREATE TABLE IF NOT EXISTS runs(
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, new_sources INTEGER,
 new_events INTEGER, new_fragments INTEGER, new_issues INTEGER);
''')
    try:
        db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS fragment_fts USING fts5(id UNINDEXED,body,tokenize="unicode61")')
    except sqlite3.OperationalError: pass
    db.commit()
    try: os.chmod(dbfile,0o600)
    except OSError: pass
    return db


def add_issue(db, source_digest, locator, code, detail, severity='warning'):
    issue_id=digest(json_text([source_digest,locator,code,detail]).encode())
    db.execute('INSERT OR IGNORE INTO issues VALUES(?,?,?,?,?,?)',
              (issue_id,source_digest,locator,severity,code,detail))


def add_fragment(db, source_digest, locator, content, extractor):
    content=str(content).strip()
    if not content: return
    # Bound the index, preserve complete original bytes in the vault.
    content=content[:30000]
    fid=digest(json_text([source_digest,locator,content]).encode())
    cur=db.execute('INSERT OR IGNORE INTO fragments VALUES(?,?,?,?,?)',
                   (fid,source_digest,locator,content,extractor))
    if cur.rowcount:
        try: db.execute('INSERT INTO fragment_fts(id,body) VALUES(?,?)',(fid,content))
        except sqlite3.OperationalError: pass


def text_file_chunks(raw: bytes, ext: str):
    try: txt=raw.decode('utf-8-sig')
    except UnicodeDecodeError: txt=raw.decode('cp1252',errors='replace')
    if ext=='.eml':
        msg=email.message_from_bytes(raw,policy=policy.default)
        parts=[f'Subject: {msg.get("subject", "")}\nFrom: {msg.get("from", "")}\nDate: {msg.get("date", "")}']
        for part in msg.walk():
            if part.get_content_type()=='text/plain':
                try: parts.append(str(part.get_content()))
                except Exception: pass
        txt='\n'.join(parts)
    elif ext in ('.html','.htm'):
        class Strip(HTMLParser):
            def __init__(self): super().__init__();self.out=[];self.skip=0
            def handle_starttag(self,tag,attrs):
                if tag in ('script','style'): self.skip+=1
            def handle_endtag(self,tag):
                if tag in ('script','style'): self.skip=max(0,self.skip-1)
            def handle_data(self,s):
                if not self.skip: self.out.append(s)
        h=Strip();h.feed(txt);txt='\n'.join(h.out)
    for index in range(0,len(txt),18000):
        yield (f'chars:{index+1}-{min(index+18000,len(txt))}',txt[index:index+18000])


def check_offline_zip(z):
    members=z.infolist()
    if len(members)>10000 or sum(x.file_size for x in members)>150_000_000:
        raise ValueError('Office archive exceeds safe offline extraction limits')
    if any(x.file_size>50_000_000 or (x.compress_size and x.file_size/x.compress_size>400)
           for x in members):
        raise ValueError('Office archive expansion ratio exceeds safe limits')


def docx_chunks(raw:bytes):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        check_offline_zip(z)
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        doc=ET.fromstring(z.read('word/document.xml'))
        for i,p in enumerate(doc.findall('.//w:p',ns),1):
            content=''.join(n.text or '' for n in p.findall('.//w:t',ns))
            if content.strip(): yield (f'paragraph:{i}',content)


def xlsx_rows(raw:bytes):
    ns={'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    rns={'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
    pkgns={'p':'http://schemas.openxmlformats.org/package/2006/relationships'}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        check_offline_zip(z)
        names=set(z.namelist())
        shared=[]
        if 'xl/sharedStrings.xml' in names:
            root=ET.fromstring(z.read('xl/sharedStrings.xml'))
            shared=[''.join(t.text or '' for t in si.findall('.//x:t',ns)) for si in root.findall('x:si',ns)]
        book=ET.fromstring(z.read('xl/workbook.xml'))
        rels={r.attrib.get('Id'):r.attrib.get('Target') for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels')).findall('p:Relationship',pkgns)}
        for sh in book.findall('.//x:sheet',ns):
            sheetname=sh.attrib['name']
            target=rels.get(sh.attrib.get('{'+rns['r']+'}id'),'')
            if target.startswith('/'): path=target.lstrip('/')
            elif target.startswith('xl/'): path=target
            else: path='xl/'+target
            if path not in names: continue
            root=ET.fromstring(z.read(path))
            rows=[]
            for row in root.findall('.//x:sheetData/x:row',ns):
                cells={}
                for cell in row.findall('x:c',ns):
                    address=cell.attrib.get('r','')
                    col=re.match(r'[A-Z]+',address)
                    if not col: continue
                    typ=cell.attrib.get('t','')
                    v=cell.find('x:v',ns)
                    if typ=='inlineStr':
                        value=''.join(t_.text or '' for t_ in cell.findall('.//x:t',ns))
                    else:
                        value=v.text if v is not None and v.text is not None else ''
                        if typ=='s' and str(value).isdigit() and int(value)<len(shared):value=shared[int(value)]
                    cells[col.group()]=value
                rows.append((int(row.attrib.get('r','0')),cells))
            yield (sheetname,rows)


def pdf_chunks(raw:bytes):
    try: from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError('PDF parser not installed locally: pip install pypdf from your approved offline wheelhouse') from exc
    reader=PdfReader(io.BytesIO(raw))
    for i,p in enumerate(reader.pages,1):
        txt=p.extract_text() or ''
        if txt.strip(): yield (f'page:{i}',txt)


def load_rules(config_path: Path) -> list:
    cfg=json.loads(config_path.read_text(encoding='utf-8'))
    rules=cfg['sources']
    if not isinstance(rules,list): raise ValueError('config.sources must be a list')
    for rule in rules:
        if rule['kind'] not in VALID_KINDS: raise ValueError(f'Unsupported record kind {rule["kind"]}')
        if not rule.get('pattern') or not isinstance(rule.get('fields'),dict): raise ValueError('Rule requires pattern and fields')
    return rules


def extract_value(row: dict,rule: dict,key: str) -> Any:
    if key in rule.get('constants',{}): return rule['constants'][key]
    f=rule['fields'].get(key)
    return row.get(f) if f is not None else None


def normalize_event(row:dict,rule:dict,source_hash:str,locator:str):
    kind=rule['kind']
    get=lambda key:extract_value(row,rule,key)
    site=str(get('site') or '').strip()
    sku=str(get('sku') or '').strip()
    period=str(get('period') or '').strip()
    if not (site and sku and period): raise ValueError('Missing site/sku/period identity; row not linked')
    occured=parse_time(get('occurred_at'))
    if not occured: raise ValueError('Missing occurred_at; cannot put event in factual timeline')
    recorded=parse_time(get('recorded_at'))
    if recorded and recorded<occured: raise ValueError('Recorded time predates occurrence; preserve as ingest issue')
    due=parse_time(get('due_at'))
    value=get('quantity')
    quantity=None
    if value not in (None,''):
        try: quantity=float(str(value).replace(',',''))
        except ValueError: raise ValueError(f'Invalid numeric quantity {value!r}')
        if not (-1e12<quantity<1e12): raise ValueError('Quantity out of supported range')
    if kind in QUANTITY_KINDS and quantity is None:
        raise ValueError(f'{kind} needs numeric quantity')
    if kind=='decision' and not (str(get('authority') or '').strip() and str(get('status') or '').lower()=='approved'):
        raise ValueError('Decision lacks approved status or named authority; cannot establish an approved target')
    record_id=str(get('record_id') or f'{source_hash[:10]}:{locator}').strip()
    evt={
        'id':digest(json_text([source_hash,locator,kind]).encode()),
        'source_digest':source_hash,'locator':locator,'case_id':str(get('case_id') or '').strip(),
        'kind':kind,'record_id':record_id,'site':site,'sku':sku,'period':period,
        'occurred_at':occured,'recorded_at':recorded,'system':str(rule.get('system') or 'unidentified'),
        'authority':str(get('authority') or '').strip(), 'quantity':quantity,
        'track':str(get('track') or '').strip(),'decision_id':str(get('decision_id') or '').strip(),
        'due_at':due,'owner':str(get('owner') or '').strip(),
        'status':str(get('status') or '').strip(), 'notes':str(get('notes') or '').strip(),
        'raw_json':json_text(row)
    }
    return evt


def import_table_row(db, row:dict,rule, source_hash, locator, count):
    add_fragment(db,source_hash,locator,json_text(row),'table-row')
    try: ev=normalize_event(row,rule,source_hash,locator)
    except (ValueError,TypeError) as exc:
        add_issue(db,source_hash,locator,'EVENT_UNMAPPED',str(exc))
        return
    cols=list(ev); values=[ev[c] for c in cols]
    db.execute('INSERT OR IGNORE INTO events ('+','.join(cols)+') VALUES ('+','.join('?' for _ in cols)+')',values)


def ingest_folder(db:sqlite3.Connection, root:Path, rules:list, workspace:Path) -> dict:
    root=root.resolve(); workspace=workspace.resolve()
    if not root.is_dir(): raise FileNotFoundError(root)
    before={name:db.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in ('sources','events','fragments','issues')}
    inspected=0
    for path in sorted(root.rglob('*')):
        if not (path.is_symlink() or path.is_file()):continue
        rel=path.relative_to(root).as_posix()
        if rel.startswith('.git/') or any(part.startswith('.') for part in path.relative_to(root).parts):continue
        def skip(reason):
            db.execute('INSERT INTO skipped_files VALUES(?,?,?) ON CONFLICT(path) DO UPDATE SET reason=excluded.reason,last_checked=excluded.last_checked',
                       (rel,reason,iso_now()))
        if path.is_symlink():skip('SYMLINK_SKIPPED_NO_FOLLOW');continue
        resolved=path.resolve()
        if root not in resolved.parents: skip('PATH_OUTSIDE_INGEST_ROOT');continue
        if workspace==resolved or workspace in resolved.parents:continue
        if path.suffix.lower() not in SUPPORTED:skip('UNSUPPORTED_FORMAT');continue
        stat=path.stat()
        if stat.st_size>75_000_000:skip('FILE_EXCEEDS_75MB_LIMIT');continue
        inspected+=1
        raw=path.read_bytes()
        stat2=path.stat()
        if stat.st_mtime_ns!=stat2.st_mtime_ns or stat.st_size!=stat2.st_size:
            skip('SOURCE_CHANGED_DURING_READ');continue
        db.execute('DELETE FROM skipped_files WHERE path=?',(rel,))
        sh=digest(raw); ext=path.suffix.lower()
        obj=workspace/'vault'/'objects'/sh
        if not obj.exists():
            # Write to temporary file, then content-address. Do not alter existing evidence.
            temp=obj.with_name(sh+'.'+uuid.uuid4().hex+'.tmp')
            temp.write_bytes(raw)
            if digest(temp.read_bytes())!=sh:raise IOError('Evidence copy failed hash check')
            os.replace(temp,obj)
            try:os.chmod(obj,0o600)
            except OSError:pass
        now=iso_now()
        db.execute('INSERT OR IGNORE INTO sources VALUES(?,?,?,?,?,?)',
                   (sh,len(raw),rel,now,ext,f'vault/objects/{sh}'))
        db.execute('INSERT INTO source_paths VALUES(?,?,?) ON CONFLICT(path,digest) DO UPDATE SET last_seen=excluded.last_seen',
                   (rel,sh,now))
        # Already-seen bytes have already been parsed; new path is retained as an alias.
        done=db.execute('SELECT COUNT(*) FROM fragments WHERE source_digest=?',(sh,)).fetchone()[0]
        problems=db.execute('SELECT COUNT(*) FROM issues WHERE source_digest=?',(sh,)).fetchone()[0]
        if done:continue
        # A previous optional extractor failure can be reattempted after
        # the offline parser is installed. The original issue stays recorded.
        rule=next((r for r in rules if Path(rel).match(r['pattern'])),None)
        try:
            if ext=='.csv':
                text=raw.decode('utf-8-sig')
                for i,row in enumerate(csv.DictReader(io.StringIO(text,newline='')),2):
                    if rule: import_table_row(db,row,rule,sh,f'csv:row:{i}',inspected)
                    else: add_fragment(db,sh,f'csv:row:{i}',json_text(row),'csv')
            elif ext=='.jsonl':
                for i,line in enumerate(raw.decode('utf-8-sig').splitlines(),1):
                    if not line.strip():continue
                    row=json.loads(line)
                    if rule and isinstance(row,dict):import_table_row(db,row,rule,sh,f'jsonl:line:{i}',inspected)
                    else:add_fragment(db,sh,f'jsonl:line:{i}',json_text(row),'jsonl')
            elif ext=='.json':
                v=json.loads(raw)
                records=v if isinstance(v,list) else v.get('records',[]) if isinstance(v,dict) else []
                if rule and isinstance(records,list):
                    for i,row in enumerate(records,1):
                        if isinstance(row,dict): import_table_row(db,row,rule,sh,f'json:index:{i}',inspected)
                else:add_fragment(db,sh,'json:root',json_text(v),'json')
            elif ext=='.docx':
                for loc,part in docx_chunks(raw):add_fragment(db,sh,loc,part,'docx')
            elif ext=='.xlsx':
                for sheet,items in xlsx_rows(raw):
                    if not items:continue
                    # Excel layout is not inferred; source mapper names actual columns.
                    header=items[0][1]
                    for i,cells in items[1:]:
                        row={label:cells.get(col,'') for col,label in header.items() if label}
                        if rule:import_table_row(db,row,rule,sh,f'xlsx:{sheet}!row:{i}',inspected)
                        else:add_fragment(db,sh,f'xlsx:{sheet}!row:{i}',json_text(row),'xlsx')
            elif ext=='.pdf':
                for loc,part in pdf_chunks(raw):add_fragment(db,sh,loc,part,'pdf')
                if not db.execute('SELECT 1 FROM fragments WHERE source_digest=?',(sh,)).fetchone():
                    add_issue(db,sh,'pdf','NO_EXTRACTABLE_TEXT','PDF has no extractable text; scanned pages need an approved local OCR engine')
            else:
                for loc,part in text_file_chunks(raw,ext):add_fragment(db,sh,loc,part,ext.lstrip('.'))
        except Exception as exc:
            add_issue(db,sh,'file','EXTRACTION_FAILED',f'{type(exc).__name__}: {exc}',severity='error')
        # Keep error history; mark a previous extraction failure resolved only
        # once the retry yielded at least one independent fragment.
        if db.execute('SELECT 1 FROM fragments WHERE source_digest=?',(sh,)).fetchone():
            for old in rows(db,'SELECT id FROM issues WHERE source_digest=? AND code="EXTRACTION_FAILED"',(sh,)):
                db.execute('INSERT OR IGNORE INTO issue_resolutions VALUES(?,?)',(old['id'],iso_now()))
    after={name:db.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in before}
    increments={name:after[name]-before[name] for name in before}
    runid=uuid.uuid4().hex[:16]
    db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',
                (runid,iso_now(),increments['sources'],increments['events'],increments['fragments'],increments['issues']))
    db.commit()
    return dict(run_id=runid,files_scanned=inspected,**{'new_'+k:v for k,v in increments.items()})


def rows(db,sql,params=()):
    return [dict(x) for x in db.execute(sql,params).fetchall()]


def source_labels(db,hashes):
    if not hashes:return {}
    sources=rows(db,'SELECT digest,original_name,byte_count FROM sources WHERE digest IN ('+','.join('?' for _ in hashes)+')',tuple(hashes))
    return {s['digest']:s for s in sources}


def evidence_ref(ev):
    return {'ref':ev['source_digest'][:16]+'@'+ev['locator'],'sha256':ev['source_digest'],
            'locator':ev['locator'],'record_id':ev['record_id'],'system':ev['system'],
            'occurred_at':ev['occurred_at'],'recorded_at':ev['recorded_at']}


def hours_between(a,b):
    if a and b:return round((t(b)-t(a)).total_seconds()/3600,2)
    return None


def recent(events,kind,asof=None,cutoff=None,by='occurred_at'):
    v=[r for r in events if r['kind']==kind and (asof is None or r['occurred_at']<=asof)
       and (asof is None or not r['recorded_at'] or r['recorded_at']<=asof)
       and (cutoff is None or r[by]<=cutoff)]
    return sorted(v,key=lambda x:(x['occurred_at'],x['recorded_at'] or '',x['id']))[-1] if v else None


def after(events,kind,decision,asof=None):
    return sorted([e for e in events if e['kind']==kind and e['occurred_at']>decision['occurred_at']
                   and (asof is None or e['occurred_at']<=asof)
                   and (asof is None or not e['recorded_at'] or e['recorded_at']<=asof)],
                  key=lambda x:(x['occurred_at'],x['recorded_at'] or '',x['id']))


def find_related_fragments(db,decision,events,limit=8):
    """Resolve candidate narrative mentions using an indexed narrative-only lookup.

    A large operational export can contain millions of structured cells that
    legitimately mention the SKU. Search those as evidence on demand, not as
    meeting-language leads during each case reconciliation.
    """
    if decision is None:return []
    identifiers=[decision['record_id'],decision['sku']]
    seen=set(); found=[]
    for term in identifiers:
        if not term:continue
        phrase='"'+term.replace('"','')+'"'
        try:
            matched=rows(db,'''SELECT f.source_digest,f.locator,f.body,s.original_name
                FROM fragment_fts ft JOIN fragments f ON f.id=ft.id
                JOIN sources s ON s.digest=f.source_digest
                WHERE fragment_fts MATCH ?
                  AND f.extractor NOT IN ('table-row','csv','jsonl','xlsx')
                LIMIT ?''',(phrase,limit*8))
        except sqlite3.OperationalError:
            matched=rows(db,'''SELECT f.source_digest,f.locator,f.body,s.original_name
                FROM fragments f JOIN sources s ON s.digest=f.source_digest
                WHERE f.extractor NOT IN ('table-row','csv','jsonl','xlsx')
                  AND lower(f.body) LIKE ? LIMIT ?''',('%'+term.casefold()+'%',limit*8))
        for match in matched:
            if match['source_digest'] in seen:continue
            if term.casefold() not in match['body'].casefold():continue
            seen.add(match['source_digest'])
            snippet=match['body'].strip().replace('\r',' ')
            if len(snippet)>340:
                idx=snippet.casefold().find(term.casefold())
                snippet=snippet[max(0,idx-80):max(0,idx-80)+340]
            found.append({'ref':match['source_digest'][:16]+'@'+match['locator'],
                          'source':match['original_name'],'snippet':snippet,
                          'relationship':'candidate_text_mention_not_execution_proof'})
            if len(found)>=limit:return found
    return found


def reconcile(db:sqlite3.Connection,asof:str|None=None):
    asof=parse_time(asof) if asof else iso_now()
    all_events=rows(db,'SELECT * FROM events ORDER BY occurred_at,recorded_at,id')
    cases={}
    for e in all_events:
        key=(e['site'],e['sku'],e['period'])
        cases.setdefault(key,[]).append(e)
    result=[]
    for (site,sku,period),evs in cases.items():
        visible=[e for e in evs if e['occurred_at']<=asof and (not e['recorded_at'] or e['recorded_at']<=asof)]
        if not visible:continue
        decisions=sorted((e for e in visible if e['kind']=='decision'),key=lambda e:(e['occurred_at'],e['recorded_at'] or ''))
        decision=decisions[-1] if decisions else None
        questions=[]
        def q(code,question,status='evidence_needed',owner='',refs=(),why='',deadline=None):
            questions.append({'code':code,'question':question,'status':status,'owner':owner,
                              'evidence':[evidence_ref(e) for e in refs if e],
                              'condition':why,'deadline':deadline})
        snaps={k:recent(visible,k) for k in VALID_KINDS}
        slots={}
        for kind in ('plan','commitment','floor'):
            if not decision:continue
            posts=after(visible,kind,decision,asof)
            match=next((e for e in posts if e['quantity']==decision['quantity']),None)
            first=posts[0] if posts else None
            latest=posts[-1] if posts else recent(visible,kind,cutoff=decision['occurred_at'])
            slots[kind]={
                'first_post_decision':evidence_ref(first) if first else None,
                'latest':evidence_ref(latest) if latest else None,
                'latest_quantity':latest['quantity'] if latest else None,
                'first_converged':evidence_ref(match) if match else None,
                'convergence_hours':hours_between(decision['occurred_at'],match['occurred_at']) if match else None,
                'detection_hours':hours_between(decision['occurred_at'],first['recorded_at']) if first and first['recorded_at'] else None,
                'delta_units':latest['quantity']-decision['quantity'] if latest else None,
                'state':('matched' if latest and latest['quantity']==decision['quantity'] else
                         'observed_different' if first else 'no_post_decision_observation')
            }
            if not first:
                q('UNOBSERVED_'+kind.upper(),f'Provide the first {kind} snapshot after the approved decision.',
                  'evidence_needed',owner={'plan':'Production planning','commitment':'Procurement','floor':'Operations'}[kind],
                  refs=[decision],why='Absence of a snapshot cannot establish non-execution')
            elif latest and latest['quantity']!=decision['quantity']:
                q('DIVERGENT_'+kind.upper(),
                  f'Why does {kind} show {latest["quantity"]:,.0f} when approved target is {decision["quantity"]:,.0f}?',
                  'investigate',owner={'plan':'Production planning','commitment':'Procurement','floor':'Operations'}[kind],
                  refs=[decision,first,latest],why='Observed post-decision value differs from approved target')
        if decision:
            priorplan=recent(visible,'plan',cutoff=decision['occurred_at'])
            priorforecast=recent(visible,'forecast',cutoff=decision['occurred_at'])
            for promise in [e for e in visible if e['kind']=='promise' and (e['decision_id']==decision['record_id'] or not e['decision_id'])]:
                track=promise['track'] or 'plan'
                if track not in ('plan','commitment','floor'):track='plan'
                target=promise['quantity'] if promise['quantity'] is not None else decision['quantity']
                matched=next((e for e in after(visible,track,decision,asof) if e['quantity']==target),None)
                if matched and promise['due_at'] and matched['occurred_at']>promise['due_at']:
                    q('PROMISE_LATE_'+promise['record_id'],
                      f'{promise["owner"] or "Owner"} promised {track} {target:,.0f} by {promise["due_at"]}; observed convergence was {matched["occurred_at"]}.',
                      'late_execution',promise['owner'],[promise,matched],
                      why='Later completion does not erase the missed commitment deadline',deadline=promise['due_at'])
                if not matched:
                    observed=after(visible,track,decision,asof)
                    conflict=next((e for e in observed if promise['due_at'] and e['occurred_at']>=promise['due_at'] and e['quantity']!=target),None)
                    due=promise['due_at']
                    q('PROMISE_'+promise['record_id'],
                      f'{promise["owner"] or "Owner"} said {track} would reach {target:,.0f} by {due or "an unspecified date"}. What is the verified execution receipt?',
                      'contradicted_by_observation' if conflict else 'receipt_missing',
                      promise['owner'],[promise,conflict] if conflict else [promise],
                      why='Statement is preserved; a verbal commitment is not execution',deadline=due)
            changed=next((e for e in after(visible,'forecast',decision,asof)),None)
            latency={k:v['convergence_hours'] for k,v in slots.items()}
            first_detection=min((v['detection_hours'] for v in slots.values() if v['detection_hours'] is not None),default=None)
            final_floor=recent(visible,'floor');inventory=recent(visible,'outcome')
            inventory_target=recent(visible,'inventory_target');unitcost=recent(visible,'unit_cost')
            excess_units=max(0,inventory['quantity']-inventory_target['quantity']) if inventory and inventory_target else None
            carrying_book_value=round(excess_units*unitcost['quantity'],2) if excess_units is not None and unitcost else None
            if inventory and not inventory_target:q('INVENTORY_TARGET_MISSING','What inventory buffer was authorized for this SKU and period?',owner='Finance',refs=[inventory])
            if inventory and inventory_target and unitcost is None:q('COST_BASIS_MISSING','What authorized cost basis should value the inventory above target?',owner='Finance',refs=[inventory,inventory_target])
            if inventory and inventory_target and excess_units is not None and excess_units>0:
                q('INVENTORY_OVER_TARGET',f'Which decisions and operational events explain {excess_units:,.0f} units above the authorized inventory target?',
                  'investigate','S&OP owner',[decision,inventory,inventory_target],
                  why='Observed inventory minus recorded inventory target; attribution to any single decision remains an investigation')
            keyfacts={
                'prior_plan':priorplan['quantity'] if priorplan else None,
                'prior_forecast':priorforecast['quantity'] if priorforecast else None,
                'approved_target':decision['quantity'],
                'target_change':decision['quantity']-priorplan['quantity'] if priorplan else None,
                'decision_time':decision['occurred_at'],
                'decision_recorded_at':decision['recorded_at'],
                'first_observed_divergence_hours':first_detection,
                'lag_to_convergence_hours':latency,
                'last_erp_snapshot_age_hours':hours_between(recent(visible,'plan')['occurred_at'],asof) if recent(visible,'plan') else None,
                'first_erp_known_lag_hours':slots.get('plan',{}).get('detection_hours'),
                'forecast_revision_to_approval_hours':hours_between(priorforecast['occurred_at'],decision['occurred_at']) if priorforecast else None,
                'decision_to_last_floor_observation_hours':hours_between(decision['occurred_at'],recent(visible,'floor')['occurred_at']) if recent(visible,'floor') else None,
                'observed_inventory_units':inventory['quantity'] if inventory else None,
                'authorized_inventory_target_units':inventory_target['quantity'] if inventory_target else None,
                'inventory_above_target_units':excess_units,
                'unit_cost_usd':unitcost['quantity'] if unitcost else None,
                'inventory_above_target_book_value_usd':carrying_book_value,
                'valuation_qualification':'Illustrative gross book value, not loss, savings, profit, or causal attribution'
            }
            if first_detection is None:q('DETECTION_CLOCK_MISSING','When was the first post-decision system state recorded?',owner='S&OP owner',refs=[decision])
        else:
            keyfacts={'approved_target':None}
            q('NO_APPROVED_DECISION','Locate an approved, attributable plan-change decision for this operational case.',owner='S&OP owner',refs=[snaps['forecast']] if snaps.get('forecast') else [])
        # Contradiction: same kind and instant, mutually incompatible quantities.
        buckets={}
        for e in visible:
            if e['kind'] not in ('plan','commitment','floor','decision'):continue
            buckets.setdefault((e['kind'],e['occurred_at'],e['system']),[]).append(e)
        for (kind,when,system),values in buckets.items():
            vals={v['quantity'] for v in values}
            if len(vals)>1:q('CONFLICT_'+kind+'_'+when, f'Conflicting {kind} quantities reported by {system} at {when}. Resolve source authority and version order.',
                         'source_conflict',system,values,why='Different quantities share same event time and system; no winner inferred')
        eventout=[]
        for e in visible:
            eventout.append({'kind':e['kind'],'record_id':e['record_id'],'quantity':e['quantity'],
                             'occurred_at':e['occurred_at'],'recorded_at':e['recorded_at'],
                             'system':e['system'],'authority':e['authority'],'owner':e['owner'],
                             'due_at':e['due_at'],'track':e['track'],'decision_id':e['decision_id'],
                             'status':e['status'],'notes':e['notes'],'evidence':evidence_ref(e)})
        result.append({'case_key':f'{site}/{sku}/{period}','site':site,'sku':sku,'period':period,
                       'decision':evidence_ref(decision) if decision else None,
                       'facts':keyfacts,'tracks':slots,'events':eventout,
                       'questions':questions,'related_documents':find_related_fragments(db,decision,visible) if decision else []})
    sources=rows(db,'SELECT * FROM sources ORDER BY original_name')
    skips=rows(db,'SELECT path,reason,last_checked FROM skipped_files ORDER BY path')
    issues=rows(db,'''SELECT i.*,s.original_name FROM issues i
                        LEFT JOIN sources s ON s.digest=i.source_digest
                        LEFT JOIN issue_resolutions z ON z.issue_id=i.id
                        WHERE z.issue_id IS NULL ORDER BY severity,code''')
    return {'schema':'decision-floor-report/0.1','source_claim':'Records are parsed from supplied exports; local hash proves byte continuity after intake, not original author or independent wall-clock truth',
            'as_of':asof,'generated_at':iso_now(),'cases':result,
            'source_count':len(sources),'event_count':len(all_events),
            'sources':sources,'issues':issues,'skipped_files':skips}


def search(db,needle,limit=20):
    needle=needle.strip()
    if not needle:return []
    out=[]
    toks=re.findall(r'[\w-]+',needle,flags=re.UNICODE)
    if toks:
        expr=' OR '.join('"'+token.replace('"','')+'"' for token in toks[:8])
        try:
            query='''SELECT f.id,f.source_digest,f.locator,f.body,s.original_name
                      FROM fragment_fts t JOIN fragments f ON f.id=t.id JOIN sources s ON s.digest=f.source_digest
                      WHERE fragment_fts MATCH ? LIMIT ?'''
            out=rows(db,query,(expr,limit))
        except sqlite3.OperationalError:out=[]
    if not out:
        out=rows(db,'''SELECT f.id,f.source_digest,f.locator,f.body,s.original_name
                      FROM fragments f JOIN sources s ON s.digest=f.source_digest
                      WHERE lower(f.body) LIKE ? LIMIT ?''',('%'+needle.lower()+'%',limit))
    return [{'ref':r['source_digest'][:16]+'@'+r['locator'],'sha256':r['source_digest'],
             'source':r['original_name'],'locator':r['locator'],'snippet':r['body'][:900]} for r in out]


def verify(db,workspace:Path):
    failures=[];checked=0
    for src in rows(db,'SELECT * FROM sources'):
        path=workspace/src['vault_relpath']
        if not path.exists():failures.append(src['digest']+':missing');continue
        if digest(path.read_bytes())!=src['digest']: failures.append(src['digest']+':hash_mismatch')
        else:checked+=1
    # Verify every event and fragment refers to an archived source.
    orphans=db.execute('''SELECT COUNT(*) FROM events e LEFT JOIN sources s ON e.source_digest=s.digest WHERE s.digest IS NULL''').fetchone()[0]
    orphans+=db.execute('''SELECT COUNT(*) FROM fragments f LEFT JOIN sources s ON f.source_digest=s.digest WHERE s.digest IS NULL''').fetchone()[0]
    if orphans:failures.append(f'{orphans} records have no source')
    return {'checked':checked,'failures':failures,'status':'PASS' if not failures else 'FAIL'}


def sync_investigations(db:sqlite3.Connection, report:dict):
    """Maintain a durable history of question state, never erasing old states.

    A current projection not generating an earlier question closes that finding
    in the *projection* only; it is not a causal or human acceptance verdict.
    """
    now=iso_now();active={}
    for case in report['cases']:
        for q in case['questions']:
            key=case['case_key'];code=q['code']
            fid=digest(json_text([key,code]).encode())
            active[fid]=(key,code,q)
    for fid,(key,code,q) in active.items():
        last=db.execute('SELECT state FROM investigation_items WHERE id=?',(fid,)).fetchone()
        before=last['state'] if last else None
        state=q['status']
        if last:
            db.execute('UPDATE investigation_items SET last_seen=?,state=?,last_question=?,owner=? WHERE id=?',
                       (now,state,q['question'],q['owner'],fid))
        else:
            db.execute('INSERT INTO investigation_items VALUES(?,?,?,?,?,?,?,?)',
                       (fid,key,code,now,now,state,q['question'],q['owner']))
        if before!=state:
            tid=uuid.uuid4().hex
            db.execute('INSERT INTO investigation_transitions VALUES(?,?,?,?,?,?,?)',
                       (tid,fid,now,before,state,'Observed source projection changed',json_text(q['evidence'])))
    for item in rows(db,'SELECT * FROM investigation_items'):
        if item['id'] in active or item['state']=='closed_in_current_projection':continue
        # Keep the history and distinguish disappearance of a condition from
        # independently verified root-cause remediation.
        db.execute('UPDATE investigation_items SET last_seen=?,state=? WHERE id=?',
                   (now,'closed_in_current_projection',item['id']))
        db.execute('INSERT INTO investigation_transitions VALUES(?,?,?,?,?,?,?)',
                   (uuid.uuid4().hex,item['id'],now,item['state'],'closed_in_current_projection',
                    'Condition absent from latest projection; closure cause not established','[]'))
    db.commit()
    return {'items':rows(db,'SELECT * FROM investigation_items ORDER BY case_key,first_seen,code'),
            'transitions':rows(db,'SELECT * FROM investigation_transitions ORDER BY happened_at,rowid')}
