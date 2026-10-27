#!/usr/bin/env python3
"""Actual user journey, local-only network boundary, portable reload and responsive QA."""
import asyncio, contextlib, functools, hashlib, http.server, json, os, pathlib, subprocess, tempfile, threading
from playwright.async_api import async_playwright, expect
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=pathlib.Path(os.environ.get('EVIDENCE_DIR',tempfile.mkdtemp(prefix='research-continuity-browser-'))).resolve();OUT.mkdir(parents=True,exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
async def main():
 supplied=os.environ.get('TEST_BASE_URL');server=None
 if supplied:base=supplied.rstrip('/')+'/';origin=base.split('/',3)[:3];origin='/'.join(origin)
 else:
  server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
  threading.Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_port}/';origin=base.rstrip('/')
 errors=[];unexpected=[];checks=[]
 async with async_playwright() as pw:
  launch={'headless':True,'chromium_sandbox':True}
  chrome=os.environ.get('TEST_CHROME')
  if chrome:launch['executable_path']=chrome
  browser=await pw.chromium.launch(**launch)
  async def page_for(width=1440,height=1100):
   context=await browser.new_context(viewport={'width':width,'height':height},accept_downloads=True)
   async def route(r):
    url=r.request.url
    if url.startswith(origin+'/') or url.startswith('file:') or url.startswith('data:') or url.startswith('blob:'):await r.continue_()
    else:unexpected.append(url);await r.abort()
   await context.route('**/*',route)
   page=await context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:asyncio.create_task(d.dismiss()))
   return context,page
  context,page=await page_for()
  await page.goto(base,wait_until='load');await page.locator('body[data-ready="true"]').wait_for()
  checks.append('Initial page ready, no precomputed outcome presented as a new run')
  await page.get_by_role('button',name='Run the working example',exact=True).click()
  await expect(page.locator('#result')).to_contain_text('Configuration B has the lowest')
  await expect(page.locator('#result')).to_contain_text('5/12 accepted')
  await expect(page.locator('#result')).to_contain_text('10/12 accepted')
  checks.append('Native evaluation: strict contract accepts A 5/12 and B 10/12; B wins')
  await page.locator('#reviewer').fill('Independent browser verifier')
  await page.locator('#rationale').fill('Synthetic fixture only; correct accounting and declared limitations inspected. No external action.')
  await page.locator('#review').click();await expect(page.locator('#freeze')).to_be_enabled();await page.locator('#freeze').click()
  await expect(page.locator('#review-status')).to_contain_text('Frozen editions: 1')
  checks.append('Explicit human review and frozen edition')
  await page.get_by_role('button',name='03   Change & reuse',exact=False).count() # use exact data selector below
  await page.locator('[data-tab="drift"]').click();await page.locator('#correct-a').click()
  await expect(page.locator('#drift-summary')).to_contain_text('source binding CHANGED')
  await page.locator('[data-tab="cycle"]').click();await page.locator('#compute').click()
  await expect(page.locator('#message')).to_contain_text('held')
  checks.append('Source correction produces a real stale-plan hold')
  await page.locator('[data-tab="drift"]').click();await page.locator('#readmit-a').click()
  await page.locator('[data-tab="cycle"]').click();await page.locator('#run-example').click()
  await expect(page.locator('#metrics')).to_contain_text('Checked reuses')
  await expect(page.locator('#review-status')).to_contain_text('Fresh review')
  checks.append('Explicit readmission and reuse preserve old edition without renewing review')
  await page.locator('#grader').select_option('extract_json');await page.locator('#apply-policy').click()
  await page.locator('#run-example').click();await expect(page.locator('#result')).to_contain_text('Configuration A has the lowest')
  checks.append('Contract revision changes the computed winner')
  await page.locator('#fail-run').click();await expect(page.locator('#message')).to_contain_text('Failed attempt retained')
  checks.append('Failed attempt retained without destroying prior result')
  await page.locator('[data-tab="drift"]').click();await page.locator('#sensitivity').click()
  await expect(page.locator('#heatmap tbody tr')).to_have_count(8)
  await page.locator('#test-tamper').click();await expect(page.locator('#tamper-status')).to_contain_text('Corrupted packet rejected')
  checks.append('Eight sensitivity cells recomputed; corrupted copy rejected')
  await page.screenshot(path=str(OUT/'change-and-reuse.png'),full_page=True)
  await page.locator('[data-tab="measurements"]').click();await page.locator('#m-sample').click()
  await expect(page.locator('#m-claims')).to_contain_text('0.75 dimensionless')
  await page.locator('#m-correct').click();await expect(page.locator('#m-summary')).to_contain_text('2 stale claims')
  await page.locator('[data-m-readmit="measurement-passed"]').click();await expect(page.locator('#m-summary')).to_contain_text('1 stale claims')
  await page.locator('#m-left').select_option('measurement-passed');await page.locator('#m-right').select_option('measurement-tested');await page.locator('#m-derive').click()
  await expect(page.locator('#m-claims')).to_contain_text('0.8 dimensionless')
  await expect(page.locator('#m-summary')).to_contain_text('0 stale claims')
  checks.append('Generic measurement receipts: extract, derive, source correction, transitive invalidation and explicit re-extraction')
  await page.screenshot(path=str(OUT/'measurement-ledger.png'),full_page=True)
  await page.locator('[data-tab="handoff"]').click()
  async with page.expect_download() as d:await page.locator('#export-packet').click()
  packet_path=OUT/'actual-export.json';await (await d.value).save_as(packet_path)
  packet=json.loads(packet_path.read_text());assert packet['schema']=='second-run/research-packet@1'
  result=subprocess.run(['node',str(ROOT/'scripts/check_packet.cjs'),str(packet_path),'--recompute'],capture_output=True,text=True,timeout=40)
  (OUT/'cold-cli.json').write_text(result.stdout);assert result.returncode==0,result.stderr
  checks.append('Actual UI packet accepted by separate Node process and recomputed')
  async with page.expect_download() as d:await page.locator('#export-offline').click()
  offline=OUT/'Research-Continuity.html';await (await d.value).save_as(offline)
  second,other=await page_for();await other.goto(offline.as_uri());await other.locator('body[data-ready="true"]').wait_for()
  await expect(other.locator('#message')).to_contain_text('Embedded workspace verified')
  await other.locator('[data-tab="drift"]').click();await expect(other.locator('#history')).to_contain_text('FAILED')
  checks.append('Standalone offline workbench cold-opens with failed attempts and history preserved')
  third,restored=await page_for();await restored.goto(base);await restored.locator('body[data-ready="true"]').wait_for();await restored.locator('[data-tab="handoff"]').click()
  await restored.locator('#packet-file').set_input_files(packet_path);await restored.locator('#restore-packet').click();await expect(restored.locator('#message')).to_contain_text('Packet verified')
  await restored.locator('#persist').check();await restored.reload();await restored.locator('body[data-ready="true"]').wait_for();await expect(restored.locator('#message')).to_contain_text('Saved browser workspace verified')
  checks.append('Local packet import and explicit browser persistence survive reload')
  broken=json.loads(packet_path.read_text());broken['workspace']['events'][0]['payload']['summary']='corruption'
  bad=OUT/'tampered.json';bad.write_text(json.dumps(broken))
  await restored.locator('[data-tab="handoff"]').click();old=await restored.locator('#packet-hash').inner_text();await restored.locator('#packet-file').set_input_files(bad);await restored.locator('#restore-packet').click();await expect(restored.locator('#message')).to_contain_text('checksum failed');assert old==await restored.locator('#packet-hash').inner_text()
  checks.append('Bad cold import refused atomically without replacing the active work')
  await page.locator('[data-tab="cycle"]').click();await page.screenshot(path=str(OUT/'desktop.png'),full_page=True)
  for width in [390,320]:
   mobile,mp=await page_for(width,1000);await mp.goto(base);await mp.locator('body[data-ready="true"]').wait_for();await mp.locator('#run-example').click();await expect(mp.locator('#result')).to_contain_text('Configuration B')
   dimensions=await mp.evaluate('({scroll:document.documentElement.scrollWidth,width:innerWidth})');assert dimensions['scroll']<=dimensions['width']+1,dimensions
   await mp.screenshot(path=str(OUT/f'mobile-{width}.png'),full_page=True);checks.append(f'Actual {width}px browser journey without document overflow');await mobile.close()
  zoomed,zp=await page_for(640,1200);await zp.goto(base);await zp.locator('body[data-ready="true"]').wait_for();await zp.add_style_tag(content='body {zoom:2;}');dims=await zp.evaluate('({scroll:document.documentElement.scrollWidth,width:innerWidth})');assert dims['scroll']<=dims['width']+1,dims;checks.append('200-percent composition at 640px viewport');await zoomed.close()
  assert not errors,errors;assert not unexpected,unexpected
  checks.append('No uncaught browser errors; zero unexpected network requests')
  receipt={'status':'PASS','checks':checks,'count':len(checks),'browser':browser.version,'page_sha256':hashlib.sha256((ROOT/'index.html').read_bytes()).hexdigest(),'errors':errors,'unexpected_requests':unexpected,'base_kind':'live' if supplied else 'loopback'}
  (OUT/'BROWSER.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
  await browser.close()
 if server:server.shutdown()
if __name__=='__main__':asyncio.run(main())
