#!/usr/bin/env python3
"""Actual public civil workbench journey, own-input use and cold succession."""
import asyncio,functools,hashlib,http.server,json,os,subprocess,tempfile,threading
from pathlib import Path
from playwright.async_api import async_playwright,expect
ROOT=Path(__file__).resolve().parent
OUT=Path(os.environ.get('EVIDENCE_DIR',tempfile.mkdtemp(prefix='civil-browser-'))).resolve();OUT.mkdir(parents=True,exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*a):pass
async def main():
 supplied=os.environ.get('TEST_BASE_URL');server=None
 if supplied:base=supplied.rstrip('/')+'/'
 else:
  server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)));threading.Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_port}/'
 origin='/'.join(base.split('/')[:3]);errors=[];network=[];checks=[]
 async with async_playwright() as p:
  b=await p.chromium.launch(headless=True,chromium_sandbox=True,executable_path=os.environ.get('TEST_CHROME') or None)
  async def fresh(width=1440,start=None):
   ctx=await b.new_context(viewport={'width':width,'height':1000},accept_downloads=True)
   async def route(r):
    if r.request.url.startswith((origin+'/', 'file:', 'blob:', 'data:')):await r.continue_()
    else:network.append(r.request.url);await r.abort()
   await ctx.route('**/*',route);page=await ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)));await page.goto(start or base);await page.locator('body[data-ready="true"]').wait_for();return ctx,page
  async def click(page,selector):
   await page.locator(selector).click();await expect(page.locator('body')).not_to_have_attribute('data-busy','true')
  ctx,page=await fresh();await expect(page.locator('h1')).to_have_text('Daily work builds the fallback.');await expect(page.locator('#capacity-classes span')).to_have_count(8);await expect(page.locator('#stages span')).to_have_count(7);checks.append('Existing eight Manzanita capacities and seven operating stages are projected from their owners')
  await click(page,'#compound');await expect(page.locator('#fabric-metrics')).to_contain_text('4/4');await expect(page.locator('#services')).to_contain_text('paper manifests');checks.append('Combined central-service loss exposes declared local paths without claiming delivered capacity')
  await click(page,'[data-loss="labor"]');await expect(page.locator('#fabric-metrics')).to_contain_text('0/4');checks.append('Missing operators hold every service even when technical paths exist')
  await click(page,'#restore-paths');await click(page,'#age-observations');await expect(page.locator('#fabric-metrics')).to_contain_text('0/4');checks.append('Aged resource observations do not silently remain available')
  await click(page,'#restore-paths');await click(page,'#run-all');await click(page,'[data-tab="food"]')
  await expect(page.locator('#owed')).to_contain_text('350');await expect(page.locator('#owed')).to_contain_text('unconfirmed');await expect(page.locator('#food-history')).to_contain_text('preassigned stock rights');checks.append('Complete exercise retains short arrival, missing acknowledgment and refused over-allocation')
  await click(page,'#partition-test');await expect(page.locator('#partition-result')).to_contain_text('RECONCILABLE');await expect(page.locator('#partition-result')).to_contain_text('HOLD');checks.append('Disjoint offline seats reconcile while cloned-writer conflicts stay held')
  await click(page,'[data-tab="power"]');await expect(page.locator('#energy-metrics')).to_contain_text('SHORTFALL');await expect(page.locator('#energy-metrics')).to_contain_text('Hour 42');await expect(page.locator('#scale-result')).to_contain_text('3,024,000');checks.append('Energy accounting exposes the actual authored deficit and distinguishes ward-wide from critical-load scale')
  await click(page,'#power-to-fabric');await click(page,'[data-tab="fabric"]');await expect(page.locator('#fabric-metrics')).to_contain_text('3/4');await expect(page.locator('#services')).to_contain_text('HOLD');checks.append('Unserved modeled energy propagates into the dependent service hold');await click(page,'[data-tab="power"]')
  await page.locator('#e-load_kw').fill('0.5');await page.locator('#e-dark_days').fill('0');await click(page,'#energy-run');await expect(page.locator('#energy-metrics')).to_contain_text('BALANCED');checks.append('Changed critical-load assumptions recompute and enter the native record')
  await click(page,'[data-tab="comms"]');await click(page,'#radio-run');await expect(page.locator('#radio-result')).to_contain_text('256');await expect(page.locator('#radio-result')).to_contain_text('NOT ESTABLISHED');checks.append('Measured full packet size and compact message budgets remain distinct from legal or RF qualification')
  await click(page,'[data-tab="fabric"]');await page.locator('#economics-input').evaluate("el=>el.closest('details').open=true");cost=json.loads(await page.locator('#economics-input').input_value());cost['shared']['administration']=2000;await page.locator('#economics-input').fill(json.dumps(cost));await click(page,'#evaluate-costs');await expect(page.locator('#economics-result')).to_contain_text('NO ADVANTAGE');checks.append('Full coordination and labor cost can overturn the proposed cooperative advantage')
  prior=await page.locator('#economics-result').inner_text();del cost['shared']['paid_labor'];await page.locator('#economics-input').fill(json.dumps(cost));await click(page,'#evaluate-costs');await expect(page.locator('#message')).to_contain_text('paid_labor');assert prior==await page.locator('#economics-result').inner_text();checks.append('Missing costs fail rather than silently becoming zero')
  await click(page,'[data-tab="basis"]');await expect(page.locator('#facility-count')).to_contain_text('76');await page.locator('#facility-search').fill('杉並第一');await expect(page.locator('#facility-table')).to_contain_text('杉並第一小学校');await expect(page.locator('#sources')).to_contain_text('Primary source');checks.append('Actual official facility data stays separate from source-qualified readiness')
  await click(page,'[data-tab="keep"]');await expect(page.locator('#field-obligations .source')).to_have_count(4)
  async with page.expect_download() as d:await click(page,'#export-packet')
  packet=OUT/'actual-civil-packet.json';await (await d.value).save_as(packet)
  q=subprocess.run(['node',str(ROOT/'packet.cjs'),str(packet)],capture_output=True,text=True,timeout=45);(OUT/'cold-packet.json').write_text(q.stdout);assert q.returncode==0,q.stderr;report=json.loads(q.stdout);assert len(report['owed'])==2 and sum(x['spent'] for x in report['stock_rights'])==660;assert report['refusals']==1 and not report['operational_ready'];assert len(report['civil_assessments'])>=4;checks.append('A fresh native consumer reconstructs actual UI decisions, all assessments and still-owed work')
  async with page.expect_download() as d:await click(page,'#export-offline')
  offline=OUT/'Civil-Continuity.html';await (await d.value).save_as(offline);await page.screenshot(path=str(OUT/'desktop.png'),full_page=True)
  await page.locator('#persist').check();await page.wait_for_timeout(250);await page.reload();await page.locator('body[data-ready="true"]').wait_for();await click(page,'[data-tab="food"]');await expect(page.locator('#owed')).to_contain_text('350');checks.append('Explicit browser persistence survives reload with obligations intact');await ctx.close()
  cold,cp=await fresh(start=offline.as_uri());await click(cp,'[data-tab="food"]');await expect(cp.locator('#owed')).to_contain_text('350');await click(cp,'[data-tab="fabric"]');await expect(cp.locator('#economics-result')).to_contain_text('NO ADVANTAGE');checks.append('Standalone offline workbench restores supply, economic and failure state without a live origin');await cold.close()
  rc,rp=await fresh();await click(rp,'[data-tab="keep"]');await rp.locator('#packet-file').set_input_files(packet);await click(rp,'#import-packet');await expect(rp.locator('#message')).to_contain_text('Packet verified');obj=json.loads(packet.read_text());obj['workspace']['events'][-1]['payload']['summary']='corrupted';bad=OUT/'bad.json';bad.write_text(json.dumps(obj));await rp.locator('#packet-file').set_input_files(bad);await click(rp,'#import-packet');await expect(rp.locator('#message')).to_contain_text('checksum');await click(rp,'[data-tab="food"]');await expect(rp.locator('#owed')).to_contain_text('350');checks.append('Bad cold import is refused atomically while current custody survives');await rc.close()
  for width in [390,320]:
   c,mp=await fresh(width);await click(mp,'#run-all')
   for section in ['fabric','food','power','comms','basis','keep']:
    await click(mp,'[data-tab="'+section+'"]');d=await mp.evaluate('({w:innerWidth,s:document.documentElement.scrollWidth})');assert d['s']<=d['w']+1,(width,section,d)
   await mp.screenshot(path=str(OUT/f'mobile-{width}.png'),full_page=True);checks.append(f'{width}px journey crosses all six work areas without horizontal overflow');await c.close()
  assert not errors,errors;assert not network,network;checks.append('No uncaught browser errors and no unexpected runtime network requests')
  result={'status':'PASS','checks':checks,'count':len(checks),'browser':b.version,'base_kind':'live' if supplied else 'loopback','page_sha256':hashlib.sha256((ROOT/'index.html').read_bytes()).hexdigest(),'errors':errors,'unexpected_requests':network};(OUT/'BROWSER.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));await b.close()
 if server:server.shutdown()
if __name__=='__main__':asyncio.run(main())
