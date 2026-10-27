#!/usr/bin/env python3
"""Actual browser origin/successor/obligation journey and offline continuation."""
import asyncio,functools,hashlib,http.server,json,os,subprocess,tempfile,threading
from pathlib import Path
from playwright.async_api import async_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('EVIDENCE_DIR',tempfile.mkdtemp(prefix='judgment-browser-'))).resolve();OUT.mkdir(parents=True,exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*a):pass
async def main():
 supplied=os.environ.get('TEST_BASE_URL');server=None
 if supplied:base=supplied.rstrip('/')+'/'
 else:
  server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)));threading.Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_port}/'
 origin='/'.join(base.split('/')[:3]);errors=[];requests=[];checks=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,chromium_sandbox=True,executable_path=os.environ.get('TEST_CHROME') or None)
  async def fresh(width=1440,start=None):
   context=await browser.new_context(viewport={'width':width,'height':1000},accept_downloads=True)
   async def gate(route):
    if route.request.url.startswith((origin+'/', 'file:', 'blob:', 'data:')):await route.continue_()
    else:requests.append(route.request.url);await route.abort()
   await context.route('**/*',gate);page=await context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:asyncio.create_task(d.dismiss()));await page.goto(start or base);await page.locator('body[data-ready="true"]').wait_for();return context,page
  ctx,page=await fresh();await expect(page.locator('#panel-judgment')).to_be_visible();await expect(page.locator('h1')).to_contain_text('Judgment that outlives');checks.append('Genesis retained judgment is the primary entry, not a secondary benchmark description')
  await page.locator('#j-load').click();await expect(page.locator('#j-now')).to_contain_text('OBSERVATION REQUIRED');await expect(page.locator('#j-open')).to_contain_text('2 unresolved');checks.append('Origin reconstructed with two obligations and expired observation currency')
  await page.locator('#j-actor').select_option('Successor operator');await page.locator('#j-time').fill('2026-10-27T10:00:00Z');await page.locator('#j-observe').click();await expect(page.locator('#j-now .big-result')).to_have_text('APPLICABLE');checks.append('Fresh declared observation establishes bounded current applicability')
  await page.locator('#j-time').fill('2026-10-27T12:00:00Z');await page.locator('#j-discharge').click();await expect(page.locator('#message')).to_contain_text('Refused and retained');await expect(page.locator('#j-open')).to_contain_text('2 unresolved');checks.append('Wrong-role discharge refuses without erasing either obligation')
  await page.locator('#j-actor').select_option('Inspector');await page.locator('#j-discharge').click();await expect(page.locator('#j-open')).to_contain_text('1 unresolved');await expect(page.locator('#j-obligations')).to_contain_text('DISCHARGED');checks.append('Case-bound inspection discharges one obligation, preserving restoration')
  await page.locator('#j-source-example').click();await expect(page.locator('#j-now')).to_contain_text('SOURCE REVIEW REQUIRED');checks.append('Source correction holds the former decision despite unchanged operating observations')
  await page.locator('#j-issue').click();await expect(page.locator('#j-now .big-result')).to_have_text('APPLICABLE');await expect(page.locator('#j-open')).to_contain_text('1 unresolved');await expect(page.locator('#j-history')).to_contain_text('SUPERSEDE');checks.append('Explicit authorized successor restores applicability while carrying unresolved obligations')
  await page.locator('#j-reviewer').fill('Synthetic acceptance reviewer');await page.locator('#j-rationale').fill('Accept this complete synthetic record for software conformance inspection only; restoration remains owed.');await page.locator('#j-freeze').click();await expect(page.locator('#j-editions')).to_contain_text('Edition 1');edition=await page.locator('#j-editions').inner_text();checks.append('Reviewed historical edition retained with its explicit limitations')
  await page.locator('#j-actor').select_option('Successor operator');await page.locator('#j-time').fill('2026-10-27T15:00:00Z');await page.locator('#j-values').fill('{"load":80,"temperature_c":40,"assembly":"B"}');await page.locator('#j-observe').click();await expect(page.locator('#j-now')).to_contain_text('CONDITION FAILED');assert edition==await page.locator('#j-editions').inner_text();checks.append('Changed operating conditions hold current use without rewriting the prior edition')
  await page.locator('#j-revision').select_option('1');await expect(page.locator('#j-open')).to_contain_text('2 unresolved');await expect(page.locator('#j-now')).to_contain_text('70 units');checks.append('Historical snapshot excludes later source changes and discharge evidence')
  await page.locator('#j-revision').select_option('current');await page.locator('#j-heat').click();await expect(page.locator('#j-heatmap td')).to_have_count(16);checks.append('Sixteen time/load assessments expose conditional and expiry boundaries')
  async with page.expect_download() as dl:await page.locator('#j-export').click()
  packet=OUT/'actual-judgment.json';await (await dl.value).save_as(packet)
  q=subprocess.run(['node',str(ROOT/'scripts/judgment_packet.cjs'),str(packet),'2026-10-27T15:00:00Z'],capture_output=True,text=True,timeout=45);(OUT/'cold-consumer.json').write_text(q.stdout);assert q.returncode==0,q.stderr;verdict=json.loads(q.stdout);assert verdict['current']['status']=='CONDITION_FAILED';assert verdict['current']['open_obligations']==1;assert verdict['refused_transitions']==1;checks.append('Fresh CLI consumer reconstructs reason, condition failure, refusal and outstanding obligation from actual UI export')
  async with page.expect_download() as dl:await page.locator('#j-offline').click()
  offline=OUT/'Retained-Judgment.html';await (await dl.value).save_as(offline)
  await page.screenshot(path=str(OUT/'judgment-desktop.png'),full_page=True);await ctx.close()
  cold,other=await fresh(start=offline.as_uri());await other.locator('body[data-ready="true"]').wait_for();await expect(other.locator('#panel-judgment')).to_have_count(1);await expect(other.locator('#j-open')).to_contain_text('1 unresolved');await expect(other.locator('#j-history')).to_contain_text('REFUSED');checks.append('Standalone file opens cold with one UI instance and complete inherited state');await cold.close()
  restore,rp=await fresh();await rp.locator('#j-import-file').set_input_files(packet);await expect(rp.locator('#message')).to_contain_text('Native journal and complete judgment transitions verified');await expect(rp.locator('#j-open')).to_contain_text('1 unresolved');checks.append('Blank successor session can directly import a retained judgment')
  obj=json.loads(packet.read_text());obj['workspace']['events'][-1]['payload']['summary']='tampered';bad=OUT/'tampered-judgment.json';bad.write_text(json.dumps(obj));await rp.locator('#j-import-file').set_input_files(bad);await expect(rp.locator('#message')).to_contain_text('checksum failed');await expect(rp.locator('#j-open')).to_contain_text('1 unresolved');checks.append('Altered import rejected atomically; current work preserved');await restore.close()
  demo,dp=await fresh();await dp.locator('#j-journey').click();await expect(dp.locator('#j-now .big-result')).to_have_text('APPLICABLE');await expect(dp.locator('#j-open')).to_contain_text('1 unresolved');await expect(dp.locator('#j-genesis-witness')).to_contain_text('ACTUAL NATIVE KERNEL RUN');checks.append('Complete one-action demonstration traverses origin, rejection, discharge, source correction and successor');await demo.close()
  for width in (390,320):
   c,mp=await fresh(width);await mp.locator('#j-journey').click();await expect(mp.locator('#j-open')).to_contain_text('1 unresolved');d=await mp.evaluate('({w:innerWidth,s:document.documentElement.scrollWidth})');assert d['s']<=d['w']+1,d;await mp.screenshot(path=str(OUT/f'judgment-{width}.png'),full_page=True);checks.append(f'{width}px complete journey has no document overflow');await c.close()
  assert not errors,errors;assert not requests,requests;checks.append('Zero uncaught page errors and zero unexpected network requests')
  report={'status':'PASS','checks':checks,'count':len(checks),'browser':browser.version,'page_sha256':hashlib.sha256((ROOT/'index.html').read_bytes()).hexdigest(),'base_kind':'live' if supplied else 'loopback','errors':errors,'unexpected_requests':requests};(OUT/'JUDGMENT-BROWSER.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));await browser.close()
 if server:server.shutdown()
if __name__=='__main__':asyncio.run(main())
