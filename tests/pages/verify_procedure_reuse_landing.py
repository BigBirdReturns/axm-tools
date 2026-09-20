"""Copy/paste entrypoint checks; independent of the fixture's task verdicts."""
import functools, http.server, json, os, pathlib, threading, re
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=pathlib.Path(os.environ.get('EVIDENCE_DIR','/tmp/axm-procedure-reuse-evidence'));OUT.mkdir(parents=True,exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args): pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
base=os.environ.get('PROCEDURE_REUSE_BASE',f'http://127.0.0.1:{server.server_port}/procedure-reuse').rstrip('/')
parts=urlsplit(base);origin=f'{parts.scheme}://{parts.netloc}'
prompt=(ROOT/'procedure-reuse/PROMPT.txt').read_text().strip()
try:
 with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True)
    context=browser.new_context(viewport={'width':1280,'height':960},permissions=['clipboard-read','clipboard-write'])
    page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base+'/');page.get_by_role('heading',name=re.compile(r'^Keep the browser\.')).wait_for()
    assert page.locator('#prompt').input_value().strip()==prompt
    page.get_by_role('button',name='Copy Hronaut prompt',exact=True).click()
    assert page.evaluate('navigator.clipboard.readText()').strip()==prompt
    assert 'Copied.' in page.locator('#copy-status').inner_text()
    page.screenshot(path=str(OUT/'landing-desktop.png'),full_page=True)
    # Explicit denial exercises the supported manual-selection fallback.
    page.evaluate("Object.defineProperty(navigator.clipboard,'writeText',{value:async()=>{throw new DOMException('Denied','NotAllowedError')}})")
    page.get_by_role('button',name='Copy Hronaut prompt',exact=True).click()
    assert 'denied' in page.locator('#copy-status').inner_text()
    assert page.locator('#prompt').evaluate('e=>e.selectionEnd-e.selectionStart')==len(page.locator('#prompt').input_value())
    page.get_by_role('link',name='Open the fixture',exact=True).click()
    assert page.url==base+'/v1/fixture.html'
    page.get_by_role('button',name='Start new test',exact=True).wait_for()
    mobile=browser.new_context(viewport={'width':390,'height':844});m=mobile.new_page();m.goto(base+'/')
    assert m.evaluate('document.documentElement.scrollWidth <= innerWidth')
    m.screenshot(path=str(OUT/'landing-mobile.png'),full_page=True)
    assert not errors,errors
    result={'copy_prompt_exact':True,'clipboard_copy':True,'clipboard_denial_fallback':True,'fixture_link':True,'mobile_no_overflow':True,'page_errors':errors,'hronaut_execution':'NOT_RUN'}
    (OUT/'landing-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    mobile.close();context.close();browser.close()
finally:
 server.shutdown();server.server_close()
