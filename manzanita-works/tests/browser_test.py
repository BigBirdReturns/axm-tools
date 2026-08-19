#!/usr/bin/env python3
from __future__ import annotations
import contextlib,http.server,json,os,socketserver,threading
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'qualification-observations';OUT.mkdir(exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
@contextlib.contextmanager
def server():
    old=os.getcwd();os.chdir(ROOT.parent)
    srv=socketserver.TCPServer(('127.0.0.1',0),Quiet);port=srv.server_address[1]
    th=threading.Thread(target=srv.serve_forever,daemon=True);th.start()
    try: yield f'http://127.0.0.1:{port}/manzanita-works/'
    finally: srv.shutdown();srv.server_close();os.chdir(old)
def assert_no_overflow(page,label):
    vals=page.evaluate('() => ({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth})')
    if vals['sw']>vals['cw']+2: raise AssertionError(f'{label} overflow {vals}')
with server() as url, sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];external=[];downloads=[]
    page.on('pageerror',lambda e: errors.append(str(e)))
    origin=url.rsplit('/manzanita-works/',1)[0]
    page.on('request',lambda r: external.append(r.url) if not r.url.startswith(origin) and not r.url.startswith(('blob:','data:')) else None)
    page.goto(url,wait_until='networkidle')
    assert page.locator('h1').inner_text()=='Manzanita Works'
    assert 'Fundraising is a view' in page.locator('.hero-sheet h2').inner_text()
    assert_no_overflow(page,'desktop initial')
    page.screenshot(path=str(OUT/'operating-fabric-desktop.png'),full_page=True)
    views=['projects','commons','pilotage','money','perimeter','architecture','handoff']
    for v in views:
        page.locator(f'.nav button[data-view="{v}"]').click()
        assert page.locator(f'.view[data-panel="{v}"]').is_visible()
        assert_no_overflow(page,f'desktop {v}')
    page.locator('.nav button[data-view="projects"]').click()
    buttons=page.locator('#project-list button');assert buttons.count()>=7
    for i in range(buttons.count()):
        label=buttons.nth(i).locator('b').inner_text();buttons.nth(i).click();assert label in page.locator('#project-detail h3').inner_text()
    page.locator('.nav button[data-view="money"]').click();assert page.locator('.money-row').count()>=5;assert page.locator('.dashboard-title strong').inner_text()=='VIEW, NOT CONSTITUTION'
    page.locator('.nav button[data-view="perimeter"]').click();page.locator('#decision-filter').select_option('WRAP');rows=page.locator('.perimeter-row:not(.head)');assert rows.count()>=3;assert all('WRAP' in rows.nth(i).inner_text() for i in range(rows.count()))
    page.locator('#decision-filter').select_option('ALL');page.locator('#perimeter-search').fill('hardware');assert page.locator('.perimeter-row:not(.head)').count()==1;assert 'Edge hardware' in page.locator('.perimeter-row:not(.head)').inner_text();page.locator('#perimeter-search').fill('')
    page.locator('.nav button[data-view="architecture"]').click();layers=page.locator('#layer-list button');assert layers.count()==6
    for i in range(layers.count()):
        label=layers.nth(i).inner_text();layers.nth(i).click();assert label==page.locator('#layer-detail h3').inner_text()
    page.locator('.nav button[data-view="handoff"]').click();page.locator('#review-note').fill('Challenge processor replacement and MyTurn custody export.')
    with page.expect_download() as dl: page.locator('#export-packet').click()
    d=dl.value;d.save_as(str(OUT/'operating-fabric-export.json'));downloads.append(d.suggested_filename)
    packet=json.loads((OUT/'operating-fabric-export.json').read_text());assert packet['schema_version']=='mw.operating-fabric.packet/0.1.0';assert 'processor replacement' in packet['local_review_note']
    page.reload(wait_until='networkidle');page.locator('.nav button[data-view="handoff"]').click();assert 'processor replacement' in page.locator('#review-note').input_value()
    page.goto(url+'?view=money',wait_until='networkidle');assert page.locator('.view[data-panel="money"]').is_visible()
    page.set_viewport_size({'width':390,'height':844});page.goto(url,wait_until='networkidle');assert_no_overflow(page,'mobile');page.screenshot(path=str(OUT/'operating-fabric-mobile.png'),full_page=True)
    page.set_viewport_size({'width':320,'height':780});page.goto(url,wait_until='networkidle');page.evaluate("document.documentElement.style.fontSize='200%'");page.wait_for_timeout(150);assert_no_overflow(page,'320 200%');page.screenshot(path=str(OUT/'operating-fabric-mobile-200pct.png'),full_page=True)
    ctx=browser.new_context(viewport={'width':900,'height':800},reduced_motion='reduce');rp=ctx.new_page();rp.goto(url,wait_until='networkidle');assert rp.evaluate("getComputedStyle(document.querySelector('.nav button')).transitionDuration") in ('0s','0.001s');ctx.close()
    if errors: raise AssertionError('browser errors: '+repr(errors))
    if external: raise AssertionError('external requests: '+repr(external))
    print('Operating Fabric browser campaign: PASS')
    print('  views:',1+len(views));print('  project drills:',buttons.count());print('  architecture layers:',layers.count());print('  packet export:',downloads[0]);print('  external requests: 0');print('  browser errors: 0')
    browser.close()
