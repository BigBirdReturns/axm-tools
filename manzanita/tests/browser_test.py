from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
LOCAL = 'http://127.0.0.1:8765/manzanita/'
TARGET = os.environ.get('MANZANITA_URL', LOCAL)
OUT = Path(os.environ.get('MANZANITA_SCREENSHOT_DIR', ROOT / 'manzanita' / 'test-output'))
OUT.mkdir(parents=True, exist_ok=True)


def exercise(page, label: str, font_scale: int = 100) -> None:
    errors=[]; outbound=[]
    page.on('pageerror', lambda exc: errors.append(f'pageerror: {exc}'))
    page.on('console', lambda msg: errors.append(f'console: {msg.text}') if msg.type == 'error' else None)
    parsed=urlparse(TARGET); origin=f'{parsed.scheme}://{parsed.netloc}'
    page.on('request', lambda req: outbound.append(req.url) if not req.url.startswith(origin) and not req.url.startswith('data:') and not req.url.startswith('blob:') else None)
    response=page.goto(TARGET, wait_until='networkidle', timeout=60000)
    assert response and response.status == 200
    if font_scale != 100:
        page.evaluate("scale => document.documentElement.style.fontSize = scale + '%'", font_scale)
    assert page.locator('html').get_attribute('data-release') == '1.6.0'
    assert page.locator('button[data-aperture]').count() == 7
    assert page.locator('[data-overlay]').count() == 8
    assert page.locator('button[data-role]').count() == 5
    assert page.locator('.estate-grid > article').count() == 6
    assets=[]
    for button in page.locator('button[data-aperture]').all():
        button.click()
        page.wait_for_timeout(60)
        assert button.get_attribute('aria-pressed') == 'true'
        assets.append(page.locator('#sceneImage').get_attribute('src'))
        assert page.locator('#apertureTitle').text_content().strip()
        assert page.locator('#authorityBoundary').text_content().strip()
        assert page.locator('#sceneClass').text_content().strip()
        image_box=page.locator('#sceneImage').bounding_box(); svg_box=page.locator('#overlaySvg').bounding_box()
        assert image_box and svg_box
        assert abs(image_box['x']-svg_box['x']) < 0.5 and abs(image_box['y']-svg_box['y']) < 0.5
        assert abs(image_box['width']-svg_box['width']) < 0.5 and abs(image_box['height']-svg_box['height']) < 0.5
    assert len(set(assets)) == 7, assets
    first=page.locator('button[data-aperture="plant"]'); first.focus(); page.keyboard.press('End')
    assert page.locator(':focus').get_attribute('data-aperture') == 'stewardship'
    assert page.locator('button[data-aperture="stewardship"]').get_attribute('aria-pressed') == 'true'
    before=page.locator('#roleAction').text_content(); page.locator('button[data-role="planner"]').click(); after=page.locator('#roleAction').text_content(); assert before != after
    assert page.locator('#roleAcceptance').text_content().strip()
    assert page.locator('#roleHandoff').text_content().strip()
    role_url=parse_qs(urlparse(page.url).query); assert role_url['role'] == ['planner']
    overlay=page.locator('[data-overlay="water"]'); old=overlay.get_attribute('aria-pressed'); overlay.click(); assert overlay.get_attribute('aria-pressed') != old
    state=parse_qs(urlparse(page.url).query, keep_blank_values=True); assert 'aperture' in state and 'layers' in state
    page.evaluate("window.print=()=>document.documentElement.dataset.printed='yes'"); page.locator('#printSheet').click(); assert page.locator('html').get_attribute('data-printed') == 'yes'
    page.evaluate("URL.createObjectURL=()=>{document.documentElement.dataset.exported='yes';return 'blob:test'};URL.revokeObjectURL=()=>{};HTMLAnchorElement.prototype.click=()=>{}")
    page.locator('#exportState').click(); assert page.locator('html').get_attribute('data-exported') == 'yes'
    old_theme=page.locator('html').get_attribute('data-theme'); page.locator('#themeToggle').click(); assert page.locator('html').get_attribute('data-theme') != old_theme
    overflow=page.evaluate('document.documentElement.scrollWidth-document.documentElement.clientWidth'); assert overflow <= 1, overflow
    assert not outbound, outbound
    assert not errors, errors
    page.screenshot(path=str(OUT / f'{label}-full.png'), full_page=True)
    page.locator('.hero').screenshot(path=str(OUT / f'{label}-hero.png'))
    page.locator('#fabric').screenshot(path=str(OUT / f'{label}-fabric.png'))

server=None
if TARGET == LOCAL:
    server=subprocess.Popen([sys.executable,'-m','http.server','8765','--bind','127.0.0.1'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    time.sleep(1)
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        for label,width,height,scale in [('desktop-light',1440,1000,100),('tablet',1024,900,100),('mobile',390,844,100),('compact-200',320,720,200)]:
            context=browser.new_context(viewport={'width':width,'height':height},device_scale_factor=1)
            exercise(context.new_page(),label,scale)
            context.close()
        browser.close()
finally:
    if server:
        server.terminate()
        with contextlib.suppress(Exception): server.wait(timeout=5)
print(f'Manzanita Works v1.6.0 browser contract: PASS ({TARGET})')
