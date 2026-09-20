"""Local browser reference. Uses existing Playwright; never talks to Hronaut."""
import contextlib, hashlib, http.server, json, os, pathlib, threading, time
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=pathlib.Path(os.environ.get('EVIDENCE_DIR', '/tmp/axm-procedure-reuse-evidence')); OUT.mkdir(parents=True,exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args): pass
handler=lambda *a,**kw: Quiet(*a,directory=str(ROOT),**kw)
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
origin=f'http://127.0.0.1:{server.server_port}'
url=origin+'/procedure-reuse/v1/fixture.html'
module=origin+'/procedure-reuse/v1/contract.mjs'

def observation(page):
    return dict(origin=page.evaluate('location.origin'),run=page.locator('#runline').get_attribute('data-run'),case=int(page.locator('#runline').get_attribute('data-case')),account=page.locator('#account').inner_text(),record=page.locator('#record').inner_text(),item=page.locator('#item').inner_text(),effect=page.locator('#effect').inner_text(),saveTargets=page.get_by_role('button',name='Save draft',exact=True).count(),quantityTargets=page.get_by_role('spinbutton',name='Quantity',exact=True).count(),dialogs=page.get_by_role('dialog').count())
def admit(page, o, binding):
    return page.evaluate('async ([url,o,b]) => (await import(url)).admit(o,b)',[module,o,binding])
def verify(page, read, binding):
    return page.evaluate('async ([url,o,b]) => (await import(url)).verify(o,b)',[module,read,binding])
def start(page):
    page.goto(url);page.get_by_role('button',name='Start new test',exact=True).click()
    return page.locator('#runline').get_attribute('data-run')

results=[];unexpected=[];errors=[]
try:
 with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_BIN') or None,args=['--disable-gpu'])
    context=browser.new_context(viewport={'width':1280,'height':960},accept_downloads=True)
    def route(r):
        if r.request.url.startswith(origin+'/') or r.request.url.startswith('blob:'): r.continue_()
        else: unexpected.append(r.request.url);r.abort()
    context.route('**/*',route)
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    run_id=start(page)
    for case,expected in enumerate(['PASS','PASS','UNKNOWN','FAIL'],1):
        binding={'origin':origin,'run':run_id,'case':case}
        o=observation(page);gate=admit(page,o,binding)
        page.screenshot(path=str(OUT/f'case-{case}-before.png'),full_page=True)
        if gate['decision']=='ADMIT':
            page.get_by_role('spinbutton',name='Quantity',exact=True).fill('3')
            # Re-read before dispatch. A cached admission is not permission to click.
            gate2=admit(page,observation(page),binding)
            assert gate2['decision']=='ADMIT',gate2
            page.get_by_role('button',name='Save draft',exact=True).click()
        page.get_by_role('button',name='Read saved record',exact=True).click()
        read=json.loads(page.get_by_label('Saved record read-back',exact=True).inner_text())
        verdict='UNKNOWN' if gate['decision']!='ADMIT' else verify(page,read,binding)['verdict']
        assert verdict==expected,(case,verdict,read)
        reasons={'PASS':'postcondition-matched','UNKNOWN':'precondition-mismatch','FAIL':'postcondition-mismatch'}
        page.get_by_label('Caller verdict',exact=True).select_option(verdict)
        page.get_by_label('Reason code',exact=True).select_option(reasons[verdict])
        page.get_by_role('button',name='Record verdict',exact=True).click()
        assert page.get_by_role('button',name='Save draft',exact=True).is_disabled()
        results.append({'case':case,'verdict':verdict,'saveAttempts':read['saveAttempts'],'externalAttempts':read['externalAttempts'],'savedQuantity':read['record']['quantity']})
        page.screenshot(path=str(OUT/f'case-{case}-after.png'),full_page=True)
        if case<4:
            page.get_by_role('button',name='Next case',exact=True).click()
            if case==1:
                page.reload();assert page.locator('#runline').get_attribute('data-run')==run_id
    receipt=json.loads(page.get_by_label('Complete fixture receipt',exact=True).inner_text())
    OUT.joinpath('reference-fixture-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    check=page.evaluate('async ([u,r])=>(await import(u)).checkReceipt(r)',[module,receipt])
    assert check['conforms'],check
    with page.expect_download() as info: page.get_by_role('button',name='Export test receipt',exact=True).click()
    downloaded=info.value;downloaded.save_as(str(OUT/'downloaded-receipt.json'))
    assert json.loads((OUT/'downloaded-receipt.json').read_text())==receipt
    # Independent caller-side recomputation from raw events, without importing the JS judge.
    for c,want in zip(receipt['cases'],['PASS','PASS','UNKNOWN','FAIL']):
        assert c['reportedVerdict']==want
        assert not [e for e in c['events'] if e['type']=='external-attempt']
        saves=[e for e in c['events'] if e['type']=='save-attempt']
        reads=[e for e in c['events'] if e['type']=='read-back']
        assert len(saves)==(0 if want=='UNKNOWN' else 1)
        assert reads and (not saves or reads[-1]['sequence']>saves[-1]['sequence'])
        assert c['readback']['record']['quantity']==(3 if want=='PASS' else 1)
    # CSS and action-target reorder is benign; unsafe semantic mutation before dispatch is not.
    q=context.new_page();rid=start(q);q.get_by_role('spinbutton',name='Quantity',exact=True).fill('3')
    q.locator('#effect').evaluate("el => el.textContent='request.submit.external'")
    assert admit(q,observation(q),{'origin':origin,'run':rid,'case':1})['decision']=='UNKNOWN'
    q.get_by_role('button',name='Read saved record',exact=True).click()
    assert json.loads(q.locator('#readback').inner_text())['saveAttempts']==0
    q.close()
    # Mobile layout and native semantic controls remain available.
    mobile=browser.new_context(viewport={'width':390,'height':844})
    m=mobile.new_page();mr=start(m)
    assert m.evaluate('document.documentElement.scrollWidth <= innerWidth')
    m.screenshot(path=str(OUT/'mobile.png'),full_page=True);mobile.close()
    summary={'schema':'axm/procedure-reuse-reference-result@1','tested_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'executor':'Python Playwright / reference fixture runner, not Hronaut','browser':browser.version,'cases':results,'four_case_contract':check,'checks':{'same_browser_context':True,'same_fixture_marker_across_reload':True,'export_roundtrip':True,'separate_python_event_crosscheck':True,'semantic_drift_rechecked_before_dispatch':True,'mobile_no_horizontal_overflow':True,'zero_unexpected_network_requests':not unexpected,'zero_browser_errors':not errors},'hronaut_execution':'NOT_RUN','workspace_generation_claim':'NOT_MADE','production_authorized':False}
    assert not unexpected,unexpected
    assert not errors,errors
    OUT.joinpath('reference-result.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    context.close();browser.close()
finally:
 server.shutdown();server.server_close()
