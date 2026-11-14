/* Optional native UI qualification. Node 22+, installed Chrome/Edge, no packages.
 * Uses a fresh temporary profile and loopback static/test server.
 * Usage: node tests/browser.mjs --out /absolute/path/outside/the/tool
 * Optional: FLYWHEEL_BROWSER=/path/to/chrome-or-edge
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import http from 'node:http';
import {fileURLToPath} from 'node:url';
import {spawn} from 'node:child_process';

const source=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const args=process.argv.slice(2);
let out;
for(let i=0;i<args.length;i++){
  if(args[i]==='--out')out=path.resolve(args[++i]);
  else throw new Error('Unknown argument: '+args[i]);
}
out ||= await fs.mkdtemp(path.join(os.tmpdir(),'agent-flywheel-ui-'));
if(out===source||out.startsWith(source+path.sep))throw new Error('QA output must be outside the distributable tool directory.');
await fs.mkdir(out,{recursive:true});
const downloadsDir=path.join(out,'downloads');
await fs.mkdir(downloadsDir,{recursive:true});
if(typeof WebSocket!=='function')throw new Error('The optional browser harness requires Node 22+ with its native WebSocket API.');
const binaries=[process.env.FLYWHEEL_BROWSER,...(process.platform==='win32'?[
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
]:['/usr/bin/google-chrome','/usr/bin/chromium','/usr/bin/chromium-browser'])].filter(Boolean);
let binary;
for(const candidate of binaries){try{await fs.access(candidate);binary=candidate;break;}catch{}}
if(!binary)throw new Error('No installed Chrome/Edge found. Set FLYWHEEL_BROWSER to an existing test binary.');

const checks=[],errors=[],browserConsoleErrors=[],requests=[],downloads=[],providerRequests=[];
const sentinel='qa-memory-only-credential-7821';
const mime={'.html':'text/html; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.md':'text/plain; charset=utf-8','.txt':'text/plain; charset=utf-8','.zip':'application/zip'};
const server=http.createServer(async(req,res)=>{
  const url=new URL(req.url,'http://localhost');
  if(req.method==='POST'&&['/__qa/error','/__qa/slow'].includes(url.pathname)){
    let body='';for await(const chunk of req)body+=chunk.toString();
    providerRequests.push({path:url.pathname,hasExpectedAuthorization:req.headers.authorization==='Bearer '+sentinel,bodyContainsCredential:body.includes(sentinel),at:Date.now()});
    if(url.pathname==='/__qa/error'){res.writeHead(503,{'Content-Type':'application/json'});res.end(JSON.stringify({error:{message:'Intentional local QA transport failure'}}));}
    else{const timer=setTimeout(()=>{if(!res.destroyed){res.writeHead(504,{'Content-Type':'application/json'});res.end(JSON.stringify({error:{message:'QA slow fixture timed out'}}));}},10000);timer.unref();res.on('close',()=>clearTimeout(timer));}
    return;
  }
  if(req.method!=='GET'&&req.method!=='HEAD'){res.writeHead(405);res.end();return;}
  try{
    const decoded=decodeURIComponent(url.pathname),filename=path.resolve(source,'.'+(decoded==='/'?'/index.html':decoded));
    if(filename!==source&&!filename.startsWith(source+path.sep)){res.writeHead(403);res.end();return;}
    const data=await fs.readFile(filename);res.writeHead(200,{'Content-Type':mime[path.extname(filename)]||'application/octet-stream','Cache-Control':'no-store'});res.end(req.method==='HEAD'?undefined:data);
  }catch{res.writeHead(404);res.end('Not found');}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const origin='http://127.0.0.1:'+server.address().port;
const profile=await fs.mkdtemp(path.join(out,'browser-profile-'));
const browser=spawn(binary,['--headless=new','--disable-background-networking','--disable-dev-shm-usage','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--remote-debugging-address=127.0.0.1','--user-data-dir='+profile,'about:blank'],{stdio:['ignore','ignore','pipe']});
let stderr='',ws,seq=0;
browser.stderr.on('data',data=>stderr+=data.toString());
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function until(fn,label='condition',milliseconds=20000){const start=Date.now();while(Date.now()-start<milliseconds){try{const value=await fn();if(value)return value;}catch{}await sleep(100);}throw new Error('Timed out waiting for '+label+'. '+stderr.slice(-1600));}
const pending=new Map();
function call(method,params={}){return new Promise((resolve,reject)=>{const id=++seq;const timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout: '+method));},20000);timer.unref();pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));});}
async function evaluate(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true,userGesture:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
async function click(selector){const found=await evaluate('(()=>{const el=document.querySelector('+JSON.stringify(selector)+');if(!el)return false;const dialog=document.querySelector(".dialog");if(dialog&&!dialog.contains(el))throw Error("Click blocked by the open evidence dialog");el.click();return true;})()');if(!found)throw new Error('Missing click target '+selector);}
async function fill(selector,value){await evaluate('(()=>{const el=document.querySelector('+JSON.stringify(selector)+');if(!el)throw Error("Missing field");el.value='+JSON.stringify(String(value))+';el.dispatchEvent(new Event("input",{bubbles:true}));el.dispatchEvent(new Event("change",{bubbles:true}));})()');}
async function go(hash){await evaluate('location.hash='+JSON.stringify(hash));await until(()=>evaluate('document.querySelector(".nav-item.active")?.dataset.view==='+JSON.stringify(hash)),'view '+hash);}
async function size(width,height){await call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<500});await sleep(250);}
async function screenshot(name){const data=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false,fromSurface:true});await fs.writeFile(path.join(out,name),Buffer.from(data.data,'base64'));}
function check(name,passed,detail){checks.push({name,passed:Boolean(passed),...(detail===undefined?{}:{detail})});if(!passed)throw new Error('UI assertion failed: '+name+(detail?' ('+JSON.stringify(detail)+')':''));}
async function viewportCheck(name){const v=await evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})');check(name,v.scroll<=v.width,v);}
async function setFile(selector,filename){const doc=await call('DOM.getDocument');const found=await call('DOM.querySelector',{nodeId:doc.root.nodeId,selector});if(!found.nodeId)throw new Error('Missing file input '+selector);await call('DOM.setFileInputFiles',{nodeId:found.nodeId,files:[filename]});}
async function downloaded(selector){const before=new Set(await fs.readdir(downloadsDir));await click(selector);return until(async()=>{const names=(await fs.readdir(downloadsDir)).filter(name=>!before.has(name)&&name.endsWith('.json'));for(const name of names){try{const filename=path.join(downloadsDir,name);return {filename,data:JSON.parse(await fs.readFile(filename,'utf8'))};}catch{}}return null;},'completed JSON download');}
async function waitTerminal(){await until(()=>evaluate('!!document.querySelector(".verification-line")&&!document.querySelector("[data-action=cancel]")'),'terminal verified result');}

let failure=null;
try{
  const port=(await until(()=>fs.readFile(path.join(profile,'DevToolsActivePort'),'utf8'),'fresh browser port')).split('\n')[0];
  const target=(await(await fetch('http://127.0.0.1:'+port+'/json/list')).json()).find(x=>x.type==='page');
  ws=new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
  ws.onmessage=event=>{const m=JSON.parse(event.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails);if(m.method==='Runtime.consoleAPICalled'&&m.params.type==='error')browserConsoleErrors.push(m.params.args.map(a=>a.value??a.description??a.type));if(m.method==='Network.requestWillBeSent')requests.push({url:m.params.request.url,method:m.params.request.method,type:m.params.type});if(m.method==='Browser.downloadWillBegin')downloads.push(m.params);const p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(new Error(JSON.stringify(m.error))):p.resolve(m.result);}};
  await call('Page.enable');await call('Runtime.enable');await call('Network.enable');await call('DOM.enable');
  await call('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:downloadsDir,eventsEnabled:true});
  await size(1440,1000);await call('Page.navigate',{url:origin});
  await until(()=>evaluate('!!document.querySelector("#goal")'),'public entry');
  check('Public empty entry',await evaluate('document.querySelector("h1").textContent==="Agent research, on demand."&&document.querySelector("#goal").value===""'));
  check('No implicit model requests',providerRequests.length===0&&requests.every(r=>r.method==='GET'));
  check('No internal service API dependency',requests.every(r=>!new URL(r.url).pathname.startsWith('/api/')));
  await viewportCheck('Desktop entry fits viewport');await screenshot('public-work-desktop.png');
  await size(390,844);await viewportCheck('Mobile entry fits viewport');await screenshot('public-work-mobile.png');
  await click('#menu-button');check('Mobile navigation opens',await evaluate('document.querySelector("#sidebar").classList.contains("open")'));
  await click('#nav-backdrop');await size(1440,1000);

  await fill('#goal','Inspect routing errors in our customer support agent.');
  await fill('#taskContract','Route customer requests using the supplied reference labels.');
  await fill('#evidenceText',JSON.stringify([{id:'qa-owned-case',input:'I was charged twice.',expected:'billing',output:'technical',split:'development'}]));
  await until(()=>evaluate('document.querySelector("#evidence-stats").innerText.includes("1 records")'),'visitor evidence parse');
  const note=path.join(out,'visitor-note.txt');await fs.writeFile(note,'Observed failure: the support agent confuses payment problems with technical problems. Literal markup <b>stays text</b>.\n');
  await setFile('#evidence-files',note);await until(()=>evaluate('document.querySelector("#file-list").innerText.includes("visitor-note.txt")'),'file upload');
  check('Visitor file and paste merged',await evaluate('document.querySelector("#evidence-stats").innerText.includes("1 records")&&document.querySelector("#evidence-stats").innerText.includes("1 source documents")'));
  await go('workflow');await click('[data-action="handoff"]');
  await until(()=>evaluate('!!document.querySelector(".handoff-preview")'),'no-key handoff');
  check('Existing-agent handoff without a key',await evaluate('document.querySelector(".handoff-preview").innerText.includes("qa-owned-case")&&document.querySelector(".handoff-preview").innerText.includes("development")'));
  check('Handoff performs no model requests',providerRequests.length===0);
  if(await evaluate('!!document.querySelector(".dialog")')){
    check('Manual copy fallback retains complete handoff',await evaluate('document.querySelector(".dialog").innerText.includes("Clipboard access is unavailable")&&document.querySelector(".dialog").innerText.includes("qa-owned-case")'));
    await screenshot('public-handoff-fallback-desktop.png');
    await click('.dialog [data-action="close-dialog"]');
  }
  await screenshot('public-workflow-desktop.png');
  const ownWork=await downloaded('[data-action="work-download"]');
  check('Visitor work export retains source',ownWork.data.schema==='axm.agent-flywheel.work.v1'&&ownWork.data.evidence.records.some(r=>r.id==='qa-owned-case')&&ownWork.data.evidence.documents.length===1);

  await go('work');await click('[data-action="sample"]');
  await until(()=>evaluate('document.querySelector("#run-budget").innerText.includes("31")'),'planned call preflight');
  check('Preflight shows call plan and cap',await evaluate('document.querySelector("#run-budget").innerText.includes("Planned calls (ceiling)")&&document.querySelector("#run-budget").innerText.includes("31")&&document.querySelector("#run-budget").innerText.includes("40")'));
  check('Demo explicitly labeled',await evaluate('document.body.innerText.includes("Synthetic example loaded.")&&document.querySelector("#run-budget").innerText.includes("Deterministic")'));
  await screenshot('public-example-work-desktop.png');
  await click('[data-action="run"]');await waitTerminal();
  check('Sample executed and verified',await evaluate('document.querySelector(".result-banner").innerText.includes("Candidate qualified")&&document.querySelector(".verification-line").innerText.includes("verified")'));
  check('Measured sample outcomes rendered',await evaluate('document.querySelector(".metrics-row").innerText.includes("2 / 4")&&document.querySelector(".metrics-row").innerText.includes("4 / 4")&&document.querySelector(".metrics-row").innerText.includes("+50 pp")'));
  check('Demo made no external model requests',providerRequests.length===0);
  await screenshot('public-result-desktop.png');
  await click('[data-action="result-tab"][data-tab="evaluation"]');
  check('Held-out comparison rendered',await evaluate('document.body.innerText.includes("Held-out reference comparison")&&document.querySelectorAll("[data-case]").length===12'));
  await screenshot('public-evaluation-desktop.png');
  await click('[data-case="0"]');check('Case inspector contains reference and outputs',await evaluate('document.querySelector(".dialog-body").innerText.includes("Supplied reference outcome")&&document.querySelector(".dialog-body").innerText.includes("Measured outputs")'));
  await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
  check('Escape closes evidence inspector',await evaluate('!document.querySelector(".dialog")'));
  await click('[data-action="result-tab"][data-tab="candidates"]');check('Selected prompt is inspectable',await evaluate('document.body.innerText.includes("Selected and frozen")&&!!document.querySelector(".candidate details[open] pre")'));
  await click('[data-action="result-tab"][data-tab="receipts"]');check('Call receipts retained',await evaluate('document.querySelectorAll(".receipt-item").length===31'));
  const sampleReport=await downloaded('[data-action="report-download"]');
  check('Complete report exported',sampleReport.data.schema==='axm.agent-flywheel.report.v1'&&sampleReport.data.verdict==='QUALIFIED'&&sampleReport.data.receipts.length===31);
  await setFile('#report-file',sampleReport.filename);await until(()=>evaluate('document.querySelector(".eyebrow").innerText.includes("IMPORTED RESEARCH REPORT")'),'verified report import');
  check('Verified report import accepted',await evaluate('document.querySelector(".verification-line").innerText.includes("verified")'));
  await size(390,844);await viewportCheck('Mobile result fits viewport');await screenshot('public-result-mobile.png');await size(1440,1000);
  const tampered=path.join(out,'tampered-report.json');await fs.writeFile(tampered,JSON.stringify({...sampleReport.data,summary:'Altered after the report was sealed.'}));await setFile('#report-file',tampered);
  await until(()=>evaluate('!!document.querySelector(".dialog")'),'invalid import feedback');
  check('Altered report rejected',await evaluate('document.querySelector(".dialog").innerText.includes("Report verification failed")&&document.querySelector(".dialog").innerText.includes("digest")'));
  await click('.dialog [data-action="close-dialog"]');

  await go('work');await fill('#preset','custom');
  await fill('#endpoint',origin+'/__qa/error');await fill('#model','qa-loopback-error');await fill('#apiKey',sentinel);
  await click('[data-action="mode"][data-mode="diagnose"]');
  check('Custom settings survive form changes',await evaluate('document.querySelector("#endpoint").value==='+JSON.stringify(origin+'/__qa/error')+'&&document.querySelector("#model").value==="qa-loopback-error"&&document.querySelector("#apiKey").value==='+JSON.stringify(sentinel)));
  await fs.rm(path.join(downloadsDir,'work.json'),{force:true});
  const keyedWork=await downloaded('[data-action="work-download"]');
  check('Memory key excluded from work export',!JSON.stringify(keyedWork.data).includes(sentinel));
  check('Credentials never persisted in web storage',await evaluate('localStorage.length===0&&sessionStorage.length===0'));
  check('Changing provider makes no model request',providerRequests.length===0);
  await click('[data-action="run"]');await waitTerminal();
  check('Provider error yields inspectable partial result',await evaluate('document.querySelector(".result-banner").innerText.includes("Research incomplete")'));
  const failedReport=await downloaded('[data-action="report-download"]');
  check('Failed report retains failure receipt',failedReport.data.status==='failed'&&failedReport.data.verdict==='INCOMPLETE'&&failedReport.data.receipts.length===1);
  check('Credential travels only in request header',providerRequests.length===1&&providerRequests[0].hasExpectedAuthorization&&!providerRequests[0].bodyContainsCredential&&!JSON.stringify(failedReport.data).includes(sentinel));

  await go('work');await fill('#endpoint',origin+'/__qa/slow');await fill('#model','qa-loopback-cancel');
  await click('[data-action="run"]');await until(()=>providerRequests.length===2,'manual slow model request');await click('[data-action="cancel"]');await waitTerminal();
  const cancelledReport=await downloaded('[data-action="report-download"]');
  check('Cancellation retains a stopped report',cancelledReport.data.status==='stopped'&&cancelledReport.data.verdict==='INCOMPLETE'&&cancelledReport.data.receipts.some(r=>r.status==='cancelled'));
  check('Cancellation report excludes credentials',!JSON.stringify(cancelledReport.data).includes(sentinel));
  await go('work');await click('[data-action="reset"]');check('Reset clears memory key',await evaluate('document.querySelector("#apiKey").value===""'));
  check('No external requests from tested paths',requests.every(r=>r.url.startsWith(origin)||r.url.startsWith('blob:'+origin)||r.url.startsWith('data:')));
  check('No uncaught JavaScript exceptions',errors.length===0,errors);
  check('No browser console errors',browserConsoleErrors.length===0,browserConsoleErrors);
}catch(error){failure={message:error.message,stack:error.stack};console.error(error.stack);}
finally{
  const report={passed:!failure&&checks.every(c=>c.passed),source,origin,browser:binary,checks,errors,browserConsoleErrors,request_count:requests.length,provider_requests:providerRequests,downloads:downloads.map(x=>({suggestedFilename:x.suggestedFilename})),failure};
  await fs.writeFile(path.join(out,'public-browser-results.json'),JSON.stringify(report,null,2)+'\n');
  const summary={passed:report.passed,checks:checks.length,failedChecks:checks.filter(c=>!c.passed),browserConsoleErrors,runtimeExceptions:errors,externalRequests:requests.filter(r=>!r.url.startsWith(origin)&&!r.url.startsWith('blob:'+origin)&&!r.url.startsWith('data:')).length,localProviderFixtureRequests:providerRequests.length,screenshots:(await fs.readdir(out)).filter(name=>name.endsWith('.png')),failure};
  await fs.writeFile(path.join(out,'public-browser-summary.json'),JSON.stringify(summary,null,2)+'\n');
  console.log(JSON.stringify(report,null,2));
  if(ws){try{await call('Browser.close');}catch{}ws.close();}
  if(browser.exitCode===null)browser.kill('SIGTERM');
  server.closeAllConnections();await new Promise(resolve=>server.close(resolve));
  if(!report.passed)process.exitCode=1;
}
