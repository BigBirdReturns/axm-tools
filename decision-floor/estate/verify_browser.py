"""Actual-page browser acceptance for the public-safe Estate action study."""
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
import argparse,functools,hashlib,importlib.util,json,os,shutil,subprocess,tempfile,threading,time,urllib.request,urllib.parse
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('owned_cdp',HERE.parent/'scripts/browser_test.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--url');parser.add_argument('--out',default=str(HERE/'browser-qualification.json'));a=parser.parse_args()
    chrome=next((shutil.which(n) for n in ('google-chrome','google-chrome-stable','chromium','chromium-browser') if shutil.which(n)),None)
    if not chrome:raise RuntimeError('Native Chromium required for this independent check')
    checks=[];server=None;cdp=None
    def require(name,value):
        checks.append({'name':name,'pass':bool(value)})
        if not value:raise AssertionError(name)
    with tempfile.TemporaryDirectory(prefix='estate-action-browser-',ignore_cleanup_errors=True) as temp:
        temp=Path(temp);profile=temp/'profile'
        with (temp/'chrome.log').open('w') as log:
            command=[chrome,'--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--remote-debugging-port=0','--user-data-dir='+str(profile),'about:blank']
            if hasattr(os,'geteuid') and os.geteuid()==0:command.append('--no-sandbox')
            proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
            try:
                for _ in range(150):
                    if (profile/'DevToolsActivePort').exists():break
                    if proc.poll() is not None:raise RuntimeError('Owned browser exited')
                    time.sleep(.1)
                port=int((profile/'DevToolsActivePort').read_text().splitlines()[0])
                tabs=json.load(urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/json'))
                cdp=module.CDP(next(t['webSocketDebuggerUrl'] for t in tabs if t['type']=='page'))
                for method in ('Runtime.enable','Network.enable','Page.enable','Log.enable'):cdp.call(method)
                if a.url:url=a.url
                else:
                    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(HERE)))
                    threading.Thread(target=server.serve_forever,daemon=True).start()
                    url='http://127.0.0.1:'+str(server.server_port)+'/index.html'
                cdp.call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
                cdp.call('Page.navigate',{'url':url})
                for _ in range(150):
                    if cdp.js("typeof STUDY_TEST==='object' && document.readyState==='complete'"):break
                    time.sleep(.1)
                require('Actual HTTP page loaded',cdp.js("typeof STUDY_TEST==='object' && document.querySelector('h1').textContent.includes('outlived')"))
                require('Restrictive network CSP',cdp.js("document.querySelector('meta[http-equiv=\"Content-Security-Policy\"]').content.includes(\"connect-src 'none'\")"))
                require('Ten choices',cdp.js("document.querySelectorAll('#case-nav button').length===10"))
                for i in range(10):
                    cdp.js('document.querySelectorAll(\"#case-nav button\")['+str(i)+'].click()')
                    require('Choice '+str(i)+' retains acceptance and proposed-only state',cdp.js('(()=>{const p=STUDY_TEST.actionPacket();return p.case_id===STUDY_TEST.data.cases['+str(i)+'].id && p.state==="PROPOSED" && p.execution_receipt===null && p.system_writeback===false && p.evidence.length>1 && p.acceptance.length>20})()'))
                cdp.js('STUDY_TEST.choose(1);document.querySelector(\"#case-sources button\").click()')
                require('Source locator opens',cdp.js("document.getElementById('source-dialog').open && document.getElementById('source-hash').textContent.length===64"))
                cdp.js("document.getElementById('close-source').click()")
                for status,code in [('completed',0),('failed',1),('usage_meter_unavailable',1)]:
                    cdp.js('document.getElementById("outcome").value='+json.dumps(status)+';STUDY_TEST.exitReplay()')
                    require('Exit mapping '+status,cdp.js('document.getElementById("exit-new").textContent==="Exit '+str(code)+'"'))
                cdp.js('document.getElementById("loads").value=100;STUDY_TEST.inputReplay()')
                require('Exact input arithmetic, no speedup claim',cdp.js('document.getElementById("input-old").textContent==="4,591,800 bytes" && document.getElementById("input-new").textContent==="575,500 bytes" && document.getElementById("input-note").textContent.includes("not measured")'))
                for snap,total in [('apply','39,829'),('later','42,095')]:
                    cdp.js('document.getElementById("snapshot").value='+json.dumps(snap)+';STUDY_TEST.versionReplay()')
                    require('Snapshot '+snap,cdp.js('document.getElementById("version-total").textContent.startsWith('+json.dumps(total)+')'))
                require('Desktop overflow absent',cdp.js('document.documentElement.scrollWidth<=innerWidth'))
                cdp.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True});time.sleep(.1)
                require('Mobile overflow absent',cdp.js('document.documentElement.scrollWidth<=innerWidth'))
                errors=[e for e in cdp.events if e.get('method')=='Runtime.exceptionThrown']
                require('No JavaScript exceptions',not errors)
                requests=[e['params']['request']['url'] for e in cdp.events if e.get('method')=='Network.requestWillBeSent']
                host=urllib.parse.urlsplit(url).netloc
                outbound=[u for u in requests if u.startswith(('http:','https:')) and urllib.parse.urlsplit(u).netloc!=host]
                require('No external application requests',not outbound)
                result={'status':'PASS','scope':'Actual public-safe page over HTTP/HTTPS; no private corpus or model run','url':url,'browser':cdp.call('Browser.getVersion')['product'],'passed':len(checks),'checks':checks,'javascript_errors':len(errors),'outbound_requests':outbound,'local_html_sha256':hashlib.sha256((HERE/'index.html').read_bytes()).hexdigest()}
                Path(a.out).write_text(json.dumps(result,indent=2)+'\n')
                print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))
            finally:
                if cdp:
                    try:cdp.call('Browser.close')
                    except (OSError,EOFError,RuntimeError):pass
                    cdp.s.close()
                try:proc.wait(timeout=12)
                except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=8)
                if server:server.shutdown();server.server_close()
if __name__=='__main__':main()
