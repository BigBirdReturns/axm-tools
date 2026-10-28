#!/usr/bin/env python3
"""Native browser interaction checks. QA-only dependency: Playwright + Chromium.
Local imports/photos never upload. Deterministic tests block eBay images; a separate
render reads the original CDN references and reports their actual availability.
"""
import argparse, functools, hashlib, http.server, json, os, tempfile, threading, zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
def run(base=None,out=None):
    out=Path(out or tempfile.mkdtemp(prefix='atmark-browser-'));out.mkdir(parents=True,exist_ok=True)
    server=None
    if not base:
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self,*a):pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
        threading.Thread(target=server.serve_forever,daemon=True).start();base='http://127.0.0.1:'+str(server.server_port)+'/'
    checks=[];errors=[]
    def good(name,value=True):
        if not value:
            page.screenshot(path=str(out/'failure.png'),full_page=True)
            (out/'failure.html').write_text(page.content())
            (out/'browser-result.json').write_text(json.dumps({'status':'FAIL','failed_check':name,'passed_checks':checks,'uncaught_errors':errors},indent=2))
        assert value,name
        checks.append(name);print('PASS',name,flush=True)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(**({'executable_path':os.environ['CHROMIUM_PATH']} if os.environ.get('CHROMIUM_PATH') else {}),headless=True,args=['--no-sandbox'])
            context=browser.new_context(viewport={'width':1440,'height':1100},accept_downloads=True)
            context.route('https://i.ebayimg.com/**',lambda r:r.abort())
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base,wait_until='networkidle');page.wait_for_selector('.product');good('53-record catalogue loads', '53 captured' in page.locator('#coverage-summary').inner_text())
            good('initial product shelf contains 16 records',page.locator('.product').count()==16)
            page.locator('#search').fill('W-1350P');good('search finds exact part',page.locator('.product').count()==1)
            page.locator('.title-button').click();good('manufacturer correction visible','Rocket Lake' in page.locator('#detail-content').inner_text());good('original generation retained','Emerald Rapids' in page.locator('#detail-content').inner_text());page.keyboard.press('Escape')
            page.locator('#clear-filters').click();page.locator('[data-category="Graphics"]').click()
            good('exact unavailable card excluded while other GPU remains',page.locator('.product[data-id="227552589910"]').count()==0 and page.locator('.product[data-id="227083143913"]').count()==1)
            page.locator('#show-ended').check();good('unavailable card can be explicitly inspected',page.locator('.product[data-id="227552589910"]').count()==1 and page.locator('.product').count()==2)
            page.locator('#clear-filters').click();page.locator('[data-compare]').nth(0).check();page.locator('[data-compare]').nth(1).check();page.locator('#compare-open').click();good('comparison shows separate configurations',page.locator('.comparison>div').count()==2);page.keyboard.press('Escape');page.locator('#compare-clear').click()
            page.locator('#search').fill('227473686089');good('wrong model image remains held',page.locator('.product-photo img').count()==0 and 'held for model review' in page.locator('.product-photo').inner_text());page.locator('#clear-filters').click()
            page.locator('[data-view="workbench"]').first.click();page.locator('#review-filter').select_option('confirmed-correction');good('exactly two source-backed corrections',page.locator('.finding').count()==2)
            testcsv='Item number,Title,Current price,Available quantity,Seller\n123456789012,"<img src=x onerror=alert(1)>, quoted",,2,atmarktradinginc\n123456789013,Unknown price,unknown,,atmarktradinginc\n123456789012,Duplicate,20,1,atmarktradinginc\nbad,Missing id,2,1,\n123456789014,Other seller,3,1,other\n'
            page.locator('#import-file').set_input_files({'name':'seller.csv','mimeType':'text/csv','buffer':testcsv.encode()});page.wait_for_function("document.querySelector('#import-status').textContent.includes('2 mapped')")
            good('import accounts for kept rejected and duplicate rows','2 mapped · 2 rejected · 1 duplicate' in page.locator('#import-status').inner_text());good('imported HTML is inert text',page.locator('#import-results img').count()==0 and '<img' in page.locator('#import-results').inner_text())
            with page.expect_download() as event:page.locator('#export-import').click()
            path=out/'import.json';event.value.save_as(path);d=json.loads(path.read_text());good('missing and nonnumeric prices stay unknown',all(i['price_min'] is None for i in d['items']));good('import source hash matches exact supplied bytes',d['source_file_sha256']==hashlib.sha256(testcsv.encode()).hexdigest())
            with page.expect_download() as event:page.locator('#export-plan').click()
            path=out/'plan.json';event.value.save_as(path);d=json.loads(path.read_text());good('review export contains every captured item and no live writes',len(d['changes'])==53 and not d['live_writes'])
            page.locator('[data-view="photos"]').first.click()
            png=page.evaluate("""async()=>{const c=document.createElement('canvas');c.width=480;c.height=320;const x=c.getContext('2d');x.fillStyle='white';x.fillRect(0,0,480,320);x.fillStyle='black';x.fillRect(0,0,40,40);x.fillText('LOCAL TEST FIXTURE',50,50);return [...new Uint8Array(await (await new Promise(r=>c.toBlob(r))).arrayBuffer())]}""")
            page.locator('#photo-file').set_input_files({'name':'test-fixture.png','mimeType':'image/png','buffer':bytes(png)});page.wait_for_selector('#photo-canvas:visible');good('photo preparation starts without approval',page.locator('#export-photo').is_disabled());good('full-frame preparation does not enlarge original',page.locator('#photo-canvas').get_attribute('width')=='480')
            page.locator('#identity-check').check();page.locator('#display-check').check();page.locator('#photo-note').fill('Automated QA fixture; not a merchandise approval.');good('both reviews and a note enable local export',page.locator('#export-photo').is_enabled());page.locator('#photo-rotation').select_option('90');good('framing changes invalidate both reviews',not page.locator('#identity-check').is_checked() and not page.locator('#display-check').is_checked());good('rotation preserves source dimensions',page.locator('#photo-canvas').get_attribute('width')=='320' and page.locator('#photo-canvas').get_attribute('height')=='480')
            page.locator('#identity-check').check();page.locator('#display-check').check()
            with page.expect_download() as event:page.locator('#export-photo').click()
            path=out/'photo.zip';event.value.save_as(path)
            with zipfile.ZipFile(path) as z:
                good('photo ZIP has valid CRCs',z.testzip() is None);r=json.loads(z.read('review.json'));good('original image preserved byte-for-byte',z.read('original.png')==bytes(png));good('derivative hash matches prepared file',r['derivative']['sha256']==hashlib.sha256(z.read('prepared.png')).hexdigest());good('photo state remains prepared not published',r['publication_state']=='prepared-not-published')
            page.locator('[data-view="take"]').first.click()
            with page.expect_download() as event:page.locator('#download-kit').click()
            path=out/'kit.zip';event.value.save_as(path)
            with zipfile.ZipFile(path) as z:good('complete source toolkit downloads with valid CRCs',z.testzip() is None and 'atmark/scripts/catalog.py' in z.namelist() and len(z.namelist())>=17)
            for width in [1440,768,390,320]:
                page.set_viewport_size({'width':width,'height':1100})
                for view in ['shop','workbench','photos','take']:
                    page.locator('[data-view="'+view+'"]').first.click();page.wait_for_timeout(60)
                    good(f'{view} fits {width}px',page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                page.locator('[data-view="shop"]').first.click();page.screenshot(path=str(out/f'shop-{width}.png'),full_page=True)
            good('no uncaught browser exceptions',not errors)
            good('spreadsheet formulas escaped',page.evaluate("ATMARK_TEST.csvCell('=1+1')").startswith('"\''))
            good('external URL host validation rejects spoofing',page.evaluate("ATMARK_TEST.safeImage('https://i.ebayimg.com.bad.test/a')") is None)
            # Separate real-source render: no mocked image bytes and no blocked CDN requests.
            live=browser.new_context(viewport={'width':1440,'height':1100});v=live.new_page()
            v.goto(base,wait_until='domcontentloaded');v.wait_for_selector('.product')
            v.evaluate("document.querySelectorAll('img').forEach(i=>i.loading='eager')")
            v.wait_for_timeout(3500)
            image_readback=v.evaluate("[...document.images].map(i=>({src:i.src,loaded:i.complete&&i.naturalWidth>0,width:i.naturalWidth,height:i.naturalHeight}))")
            v.screenshot(path=str(out/'shop-real-images-1440.png'),full_page=True)
            v.set_viewport_size({'width':390,'height':1000});v.screenshot(path=str(out/'shop-real-images-390.png'),full_page=True)
            (out/'real-image-readback.json').write_text(json.dumps(image_readback,indent=2))
            browser.close()
        result={'status':'PASS','checks':len(checks),'names':checks,'uncaught_errors':errors,'scope':'Actual UI on HTTP. Deterministic interaction tests block eBay images; separate screenshots and availability records use real CDN references.','real_image_readback':{'remaining_img_elements':len(image_readback),'loaded':sum(i['loaded'] for i in image_readback)},'base':base}
        (out/'browser-result.json').write_text(json.dumps(result,indent=2));return result
    finally:
        if server:server.shutdown()
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--base');a.add_argument('--out');v=a.parse_args();print(json.dumps(run(v.base,v.out),indent=2))
