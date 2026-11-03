#!/usr/bin/env python3
"""Real browser/CSP/UI acceptance using stdlib and an installed Chromium binary."""
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
import argparse,base64,contextlib,functools,hashlib,json,os,shutil,socket,struct,subprocess,tempfile,threading,time,urllib.request,urllib.parse
ROOT=Path(__file__).resolve().parents[1]
class CDP:
    def __init__(self,url):
        u=urllib.parse.urlsplit(url)
        if u.hostname not in ('localhost','127.0.0.1'):raise ValueError('Only the owned local browser endpoint is admitted')
        self.s=socket.create_connection((u.hostname,u.port),timeout=15);self.s.settimeout(20);self.buf=b'';self.seq=0;self.events=[]
        key=base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f'GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        data=b''
        while b'\r\n\r\n' not in data:data+=self.s.recv(8192)
        h,self.buf=data.split(b'\r\n\r\n',1)
        if not h.startswith(b'HTTP/1.1 101'):raise RuntimeError(h.decode(errors='replace'))
        expected=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
        if expected not in h:raise RuntimeError('WebSocket handshake failed')
    def read(self,n):
        while len(self.buf)<n:
            b=self.s.recv(max(8192,n-len(self.buf)))
            if not b:raise EOFError('Owned browser closed its socket')
            self.buf+=b
        b,self.buf=self.buf[:n],self.buf[n:];return b
    def frame(self,body,opcode=1):
        b=body.encode() if isinstance(body,str) else body;n=len(b);mask=os.urandom(4)
        hdr=bytes([0x80|opcode,0x80|n]) if n<126 else bytes([0x80|opcode,0x80|126])+struct.pack('!H',n) if n<65536 else bytes([0x80|opcode,0x80|127])+struct.pack('!Q',n)
        self.s.sendall(hdr+mask+bytes(v^mask[i%4] for i,v in enumerate(b)))
    def message(self):
        parts=[]
        while True:
            a,b=self.read(2);n=b&127
            if n==126:n=struct.unpack('!H',self.read(2))[0]
            elif n==127:n=struct.unpack('!Q',self.read(8))[0]
            mask=self.read(4) if b&128 else None;raw=self.read(n)
            if mask:raw=bytes(v^mask[i%4] for i,v in enumerate(raw))
            op=a&15
            if op==8:raise EOFError('Browser closed')
            if op==9:self.frame(raw,10);continue
            if op in (0,1):parts.append(raw)
            if a&128 and op in (0,1):return json.loads(b''.join(parts))
    def call(self,method,params=None):
        self.seq+=1;id=self.seq;self.frame(json.dumps({'id':id,'method':method,'params':params or {}}))
        while True:
            m=self.message()
            if m.get('id')==id:
                if 'error' in m:raise RuntimeError(method+': '+str(m['error']))
                return m.get('result',{})
            self.events.append(m)
    def js(self,expression):
        r=self.call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
        if 'exceptionDetails' in r:raise RuntimeError(str(r['exceptionDetails']))
        return r.get('result',{}).get('value')
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default=str(ROOT/'data/browser-qualification.json'));ap.add_argument('--url');args=ap.parse_args()
    chrome=next((shutil.which(n) for n in ('google-chrome','google-chrome-stable','chromium','chromium-browser') if shutil.which(n)),None)
    if not chrome:raise SystemExit('Chromium is required for this separate browser qualification; product runtime is unaffected.')
    checks=[];errors=[];started=time.monotonic();server=None
    def require(name,condition,detail=None):
        checks.append({'name':name,'pass':bool(condition),'observed':detail})
        if not condition:raise AssertionError(name+': '+str(detail))
    with tempfile.TemporaryDirectory(prefix='decision-floor-browser-') as td:
        td=Path(td);profile=td/'profile';log=(td/'chrome.log').open('w')
        cmd=[chrome,'--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--remote-debugging-port=0','--user-data-dir='+str(profile),'about:blank']
        if hasattr(os,'geteuid') and os.geteuid()==0:cmd.append('--no-sandbox')
        proc=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
        cdp=None
        try:
            portfile=profile/'DevToolsActivePort'
            for _ in range(150):
                if portfile.exists():break
                if proc.poll() is not None:raise RuntimeError('Browser stopped: '+(td/'chrome.log').read_text()[-3000:])
                time.sleep(.1)
            port=int(portfile.read_text().splitlines()[0]);tabs=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json'))
            cdp=CDP(next(x['webSocketDebuggerUrl'] for x in tabs if x['type']=='page'))
            version=cdp.call('Browser.getVersion')
            for method in ['Runtime.enable','Page.enable','Network.enable','Log.enable']:cdp.call(method)
            cdp.call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})
            if args.url:url=args.url
            else:
                server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
                threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}/index.html'
            cdp.call('Page.navigate',{'url':url})
            for _ in range(150):
                if cdp.js("typeof window.DF_TEST==='object' && document.readyState==='complete'"):break
                time.sleep(.1)
            require('Actual static page loaded with CSP',cdp.js("typeof DF_TEST==='object' && document.querySelector('meta[http-equiv=\"Content-Security-Policy\"]').content.includes(\"connect-src 'none'\")"))
            q=lambda id:cdp.js('document.getElementById('+json.dumps(id)+').textContent')
            click=lambda id:cdp.js('document.getElementById('+json.dumps(id)+').click()')
            require('First recorded PO discrepancy',q('gap').startswith('+5,000') and q('lag')=='4h 15m',[q('gap'),q('lag')])
            require('Explicit book-cost comparison',q('capital')=='$210,000' and 'not an inventory count' in q('capital-note'))
            require('Unknown floor remains unknown',cdp.js("document.querySelectorAll('.node')[4].textContent.includes('No receipt')"))
            require('Desktop has no horizontal overflow',cdp.js('document.documentElement.scrollWidth<=innerWidth'))
            cdp.js('DF_TEST.setMoment(0)')
            require('No future approval leaks into baseline',q('target')=='–' and 'Not independently measurable' in q('ttd-result'),[q('target'),q('ttd-result')])
            cdp.js('DF_TEST.setMoment(1)')
            require('Agreement does not imply implementation',q('gap')=='–' and 'Awaiting execution receipt' in q('promises'))
            cdp.js('DF_TEST.setMoment(2)');click('answer')
            require('Question carries source evidence links',cdp.js("document.querySelectorAll('#receipt-content [data-evidence]').length>=2"))
            cdp.js("document.querySelector('#receipt-content [data-evidence]').click()")
            require('Source modal contains original bytes and digest',cdp.js("!!document.querySelector('#receipt-content pre') && document.querySelector('#receipt-content .hash').textContent.length===64"))
            click('close-dialog');cdp.js("document.getElementById('search').value='PO-908-2';document.getElementById('search').dispatchEvent(new Event('input'))")
            require('Evidence search filters exact record',cdp.js("document.querySelectorAll('#ledger-rows tr').length===1 && document.querySelector('#ledger-rows').textContent.includes('PO-908-2')"))
            cdp.js("document.getElementById('search').value='';document.getElementById('search').dispatchEvent(new Event('input'))")
            click('mode-closed');cdp.js('DF_TEST.setMoment(4)')
            require('Independent closed-loop receipts converge',q('gap').startswith('0') and q('capital')=='$0' and q('action-title')=='The records agree. Preserve the path.')
            click('verify')
            for _ in range(40):
                if 'source hashes match' in q('receipt-title'):break
                time.sleep(.05)
            require('All original synthetic files rehash',q('receipt-title')=='12 source hashes match',q('receipt-title'));click('close-dialog')
            for text in ['', 'abc', '日本語 / supply chain / 123', 'abcdef'*1000]:
                actual=cdp.js('DF_TEST.sha('+json.dumps(text)+')');require('SHA-256 reference '+str(len(text)),actual==hashlib.sha256(text.encode()).hexdigest())
            click('mode-missed');cdp.js('DF_TEST.setMoment(4)')
            require('Outcome measured against explicit policy',q('capital')=='$210,000' and 'Book value, not realized loss' in q('capital-note'))
            click('new-case')
            for _ in range(40):
                if cdp.js('DF_TEST.getState().generated'):break
                time.sleep(.05)
            require('New case has new entities and values',cdp.js("DF_TEST.getState().generated && DF_TEST.caseData().sku.startsWith('ITEM-') && DF_TEST.caseData().events.every(e=>e.evidence.sha256.length===64)"))
            # Real file-picker change path; the fixture is supplied locally through DOM File APIs.
            cdp.js("window.__inputReport={schema:'decision-floor-report/0.1',cases:[JSON.parse(JSON.stringify(DF_DATA.cases.missed.case))]};window.__feedReport=async r=>{const input=document.getElementById('report-file'),dt=new DataTransfer();dt.items.add(new File([JSON.stringify(r)],'decision_floor_report.json',{type:'application/json'}));input.files=dt.files;await input.onchange();};")
            cdp.js('window.__feedReport(window.__inputReport)')
            require('Local file import works without upload',cdp.js('DF_TEST.getState().imported') and 'Original bytes remain' in q('verify') and q('capital')=='$210,000')
            cdp.js("window.__bad=JSON.parse(JSON.stringify(__inputReport));__bad.cases[0].events[0].occurred_at='2026-10-05T00:00:00';__feedReport(__bad)")
            require('Timezone-free input rejected',q('notice').startswith('Report not opened:'))
            cdp.js("window.__bad=JSON.parse(JSON.stringify(__inputReport));const d=__bad.cases[0].events.find(e=>e.kind==='decision');__bad.cases[0].events.push({...d,record_id:'CONFLICT-DECISION',quantity:d.quantity+1});__feedReport(__bad)")
            require('Conflicting approvals are refused',q('notice').startswith('Report not opened:') and 'unambiguous' in q('notice'))
            cdp.js("window.__bad=JSON.parse(JSON.stringify(__inputReport));__bad.cases[0].sku='<img src=x onerror=window.__xss=1>';__feedReport(__bad)")
            require('Imported labels cannot execute markup',cdp.js("!window.__xss && !document.getElementById('sku').querySelector('img')"))
            click('mode-missed');cdp.js('DF_TEST.setMoment(2)')
            # Reset generated data by returning to the original page for a faithful share preview.
            cdp.call('Page.navigate',{'url':url})
            for _ in range(100):
                if cdp.js("typeof DF_TEST==='object' && document.readyState==='complete'"):break
                time.sleep(.1)
            assets=ROOT/'assets';assets.mkdir(exist_ok=True)
            metrics=cdp.call('Page.getLayoutMetrics')['cssContentSize']
            png=cdp.call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True,'clip':{'x':0,'y':0,'width':1440,'height':min(metrics['height'],10000),'scale':1}})['data']
            (assets/'preview.png').write_bytes(base64.b64decode(png))
            cdp.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True});time.sleep(.15)
            require('390px mobile layout has no horizontal overflow',cdp.js('document.documentElement.scrollWidth<=innerWidth'))
            errors=[e for e in cdp.events if e.get('method')=='Runtime.exceptionThrown']
            requests=[e['params']['request']['url'] for e in cdp.events if e.get('method')=='Network.requestWillBeSent']
            expected=urllib.parse.urlsplit(url).netloc
            unexpected=[u for u in requests if u.startswith(('http://','https://')) and urllib.parse.urlsplit(u).netloc!=expected]
            require('No JavaScript exceptions',not errors,errors)
            require('No outbound application requests',not unexpected,unexpected)
            require('No CSP script or style failures',not [e for e in cdp.events if e.get('method')=='Log.entryAdded' and e.get('params',{}).get('entry',{}).get('source')=='security'],None)
            receipt={'status':'PASS','scope':'Actual Chromium page, CSP, DOM interaction and local file import; synthetic records only','browser':version['product'],'checks':checks,'passed':sum(x['pass'] for x in checks),'javascript_errors':len(errors),'outbound_requests':unexpected,'elapsed_seconds':round(time.monotonic()-started,2),'network_boundary':'Initial static resources only; local import remained in browser memory','customer_integration':'Not exercised'}
            out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
        finally:
            if cdp:cdp.s.close()
            if server:server.shutdown();server.server_close()
            proc.terminate()
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
            log.close()
if __name__=='__main__':main()
