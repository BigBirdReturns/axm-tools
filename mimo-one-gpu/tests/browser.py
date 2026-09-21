"""Browser qualification of the handoff, not MiMo inference or benchmark quality."""
import functools, hashlib, http.server, json, os, pathlib, re, threading, time, urllib.parse
from playwright.sync_api import sync_playwright, expect
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = pathlib.Path(os.environ.get('EVIDENCE_DIR', '/tmp/mimo-one-gpu-evidence')); OUT.mkdir(parents=True, exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args): pass
server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(ROOT)))
threading.Thread(target=server.serve_forever, daemon=True).start()
base = os.environ.get('PUBLIC_BASE', f'http://127.0.0.1:{server.server_port}').rstrip('/')
origin = urllib.parse.urlsplit(base).netloc
checks = {}
try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=os.environ.get('CHROMIUM_BIN') or None)
        ctx = browser.new_context(viewport={'width':1440, 'height':1000}, permissions=['clipboard-read', 'clipboard-write'], accept_downloads=True, reduced_motion='reduce')
        page = ctx.new_page(); errors = []; unexpected = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('request', lambda r: unexpected.append(r.url) if urllib.parse.urlsplit(r.url).netloc != origin and not r.url.startswith(('blob:', 'data:')) else None)
        page.goto(base+'/', wait_until='domcontentloaded')
        page.get_by_role('heading', name=re.compile(r'^One GPU\.')).wait_for()
        assert 'NOT YET RUN' in page.locator('body').inner_text()
        assert page.locator('#prompt').input_value().strip() == (ROOT/'PROMPT.txt').read_text().strip()
        checks['default_prompt_exact'] = True
        page.screenshot(path=str(OUT/'desktop-hero.png'))
        page.screenshot(path=str(OUT/'desktop-full.png'), full_page=True)
        page.get_by_role('button', name='Copy the local-agent test', exact=False).click()
        copied = page.evaluate('navigator.clipboard.readText()')
        assert 'MiMo-V2.6-Pro-RL' in copied and '--approve-load' in copied and 'A BLOCKED plan stays blocked' in copied
        checks['clipboard_copy'] = True
        page.get_by_label('Model checkpoint', exact=True).select_option('XiaomiMiMo/MiMo-V2.6-Flash-RL')
        assert page.locator('#total-params').inner_text() == '309B'
        page.get_by_label('Where to start', exact=True).select_option('native')
        page.get_by_label('Benchmark or harness', exact=False).fill('My native GPQA protocol')
        page.get_by_role('button', name='Copy prompt', exact=True).click()
        copied = page.evaluate('navigator.clipboard.readText()')
        assert 'Requested next mode: native' in copied and 'My native GPQA protocol' in copied and 'for XiaomiMiMo/MiMo-V2.6-Flash-RL' in copied
        checks['model_route_and_benchmark_preserved'] = True
        page.get_by_label('Where to start', exact=True).select_option('offline')
        assert 'Only independent' in page.locator('#route-note').inner_text()
        checks['offline_route_boundary'] = True
        with page.expect_download() as info:
            page.get_by_role('button', name='Save as text', exact=False).click()
        download = info.value; download.save_as(str(OUT/'prompt-export.txt'))
        assert (OUT/'prompt-export.txt').read_text().strip() == page.locator('#prompt').input_value().strip()
        checks['prompt_export_exact'] = True
        with page.expect_download() as info:
            page.get_by_role('link', name='Download complete kit', exact=False).click()
        info.value.save_as(str(OUT/'kit-download.zip'))
        assert hashlib.sha256((OUT/'kit-download.zip').read_bytes()).digest() == hashlib.sha256((ROOT/'mimo-one-gpu-kit.zip').read_bytes()).digest()
        checks['kit_download_exact'] = True
        page.locator('#source').scroll_into_view_if_needed()
        expect(page.locator("#source-status")).to_have_text(re.compile(r"^Read-only preview"))
        for file in ['v1/README.md','v1/one_gpu.py','v1/bridge.py','tests/test_lab.py','v1/settings.example.json','v1/protocol.example.json','SOURCE-MANIFEST.json','SOURCES.json']:
            page.locator(f'button[data-file="{file}"]').click()
            expected = (ROOT/file).read_text()
            expect(page.locator("#source-code")).to_have_text(expected)
            assert page.locator("#source-code").text_content() == expected
            assert page.locator('#source-raw').get_attribute('href') == file
        checks['all_eight_source_previews_exact'] = True
        # A malicious-looking benchmark label remains text in the brief.
        page.locator('#benchmark').fill('<script>window.bad=1</script>')
        assert page.evaluate('window.bad') is None
        assert '<script>window.bad=1</script>' in page.locator('#prompt').input_value()
        checks['input_remains_plain_text'] = True
        page.locator('#benchmark').fill('My native GPQA protocol')
        page.evaluate("Object.defineProperty(navigator.clipboard,'writeText',{value:async()=>{throw new DOMException('Denied','NotAllowedError')}})")
        page.get_by_role('button', name='Copy prompt', exact=True).click()
        assert 'denied' in page.locator('#copy-status').inner_text()
        assert page.locator('#prompt').evaluate('e=>e.selectionEnd-e.selectionStart') == len(page.locator('#prompt').input_value())
        checks['clipboard_denial_fallback'] = True
        # Verify an unavailable static file surfaces an error, not an empty success.
        page.route('**/v1/bridge.py', lambda r: r.fulfill(status=503, body='unavailable'))
        page.locator('button[data-file="v1/bridge.py"]').click()
        expect(page.locator("#source-status")).to_have_text(re.compile(r"^Read failed"))
        checks['source_read_failure_visible'] = True
        page.unroute('**/v1/bridge.py')
        page.locator('button[data-file="v1/one_gpu.py"]').click()
        expect(page.locator("#source-status")).to_have_text(re.compile(r"^Read-only preview"))
        page.locator('#configure').scroll_into_view_if_needed()
        page.screenshot(path=str(OUT/'desktop-workbench.png'))
        for width in [360, 390, 768, 1440]:
            page.set_viewport_size({'width':width, 'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
        checks['four_viewports_no_horizontal_overflow'] = True
        page.set_viewport_size({'width':390, 'height':844}); page.evaluate('scrollTo(0,0)')
        page.screenshot(path=str(OUT/'mobile-hero.png'))
        page.screenshot(path=str(OUT/'mobile-full.png'), full_page=True)
        assert not errors, errors
        assert not unexpected, unexpected
        checks['no_page_errors'] = True; checks['no_external_page_requests'] = True
        result = {'schema':'axm/mimo-one-gpu-browser-check@2', 'tested_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'base':base, 'browser':browser.version, 'checks':checks, 'native_mimo':'NOT_RUN', 'benchmark_scores':'NOT_MEASURED'}
        (OUT/'browser.json').write_text(json.dumps(result, indent=2)+'\n'); print(json.dumps(result, indent=2))
        ctx.close(); browser.close()
finally:
    server.shutdown(); server.server_close()
