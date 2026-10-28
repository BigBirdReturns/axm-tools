// Exercise the actual embedded generators with a stable fixture independent of curation.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
const start=html.indexOf('function buildBoardReport(');
const controls=html.indexOf('const clearReportBtn=',start);
const speechStart=html.indexOf('function buildSpeakingScript(',controls);
const generateStart=html.indexOf('document.getElementById("gen").onclick=',speechStart);
const scope={inSchoolScope:c=>!c.schools||c.schools.includes('ha')};
vm.createContext(scope);
vm.runInContext(html.slice(start,controls)+html.slice(speechStart,generateStart),scope);
const now=new Date(2026,9,28,12);
const p={
  board_report:{reviewed_on:'2026-10-28',review_by:'2026-10-30',card_ids:['a','m'],
    disposition:'For information only.',request:'Please allow a report slot.',
    spoken_intro:'Here is the update.',spoken_request:'Please send questions.',
    limitations:['The agenda is not outcome evidence.'],closing:'Questions welcome.',
    followups:[{what:'Review outcome',owner:'VP',due:'2026-10-30',status:'open'},{what:'Finished task',status:'done'}],
    resources:[{label:'PTA alerts',url:'https://capta.org/advocacy/take-action/'}]},
  in_effect:[{id:'a',title:'Adopted plan',report_summary:'The plan was approved.',spoken_summary:'A plan is approved.',
    reviewed_on:'2026-09-21',source_url:'https://example.test/plan',verification_url:'https://example.test/recording'}],
  coming_up:[{id:'m',title:'October 27 meeting',until:'2026-10-27',reviewed_on:'2026-10-28',
    source_url:'https://example.test/agenda',report_summary:'The next meeting is October 27.',spoken_summary:'Tomorrow is the meeting.'}]
};
const report=scope.buildBoardReport(p,now);
assert.match(report,/^PTA LEGISLATION UPDATE - DRAFT/);
for(const text of ['Review by 2026-10-30','REQUEST','OPEN FOLLOW-UPS','Review outcome','LIMITATIONS','RESOURCES','PTA alerts','SOURCES','Vote confirmation'])assert.ok(report.includes(text),text);
assert.doesNotMatch(report,/Finished task|The next meeting is October 27/);
assert.match(report,/Follow-up required: October 27 meeting/);
const spoken=scope.buildSpeakingScript(p,now);
assert.match(spoken,/A plan is approved/);
assert.match(spoken,/Follow-up required/);
assert.match(spoken,/Please send questions/);
assert.doesNotMatch(spoken,/Tomorrow is the meeting/);
for(const date of [new Date(2026,9,27),new Date(2026,9,31)]){
  assert.match(scope.buildBoardReport(p,date),/^REVIEW REQUIRED/);
  assert.match(scope.buildSpeakingScript(p,date),/^REVIEW REQUIRED/);
}
for(const bad of ['2026-99-99','2026-02-30','not-a-date']){
  const x=structuredClone(p);x.board_report.reviewed_on=bad;
  assert.match(scope.buildBoardReport(x,now),/^REVIEW REQUIRED/);
}
for(const [field,value] of [['reviewed_on','2026-10-29'],['review_by','2026-10-27']]){
  const x=structuredClone(p);x.board_report[field]=value;
  assert.match(scope.buildBoardReport(x,now),/^REVIEW REQUIRED/);
}
for(const mutate of [x=>x.board_report.card_ids=['missing'],x=>x.board_report.card_ids=[],
  x=>x.board_report.card_ids=['a','a','a','a','a'],x=>delete x.in_effect[0].source_url,
  x=>x.in_effect[0].schools=['other'],x=>x.in_effect[0].reviewed_on='2026-10-29',
  x=>x.in_effect[0].reviewed_on='2026-02-30']){
  const x=structuredClone(p);mutate(x);assert.match(scope.buildBoardReport(x,now),/^REVIEW REQUIRED/);
}
assert.match(scope.buildBoardReport(null,now),/unavailable/);
console.log('PASS: independent fixture, dates, school scope, sources, historical receipts, pending outcomes and speaking script');

const ids=['gen','clear-report','speech','print-report','meeting-date','speech-report','speech-label'];
const elements=Object.fromEntries(ids.map(id=>[id,{style:{},value:'',textContent:'',focus(){this.focused=true;}}]));
const classes=new Set(),events={};let printCalls=0,clipboardText='';
scope.document={getElementById:id=>elements[id],body:{classList:{add:x=>classes.add(x),remove:x=>classes.delete(x)}}};
scope.report={style:{},textContent:''};scope.copyBtn={style:{},textContent:''};scope.shareBtn={style:{}};
scope.t=k=>k;scope.navigator={share(){},clipboard:{writeText(text){clipboardText=text;return Promise.resolve();}}};
scope.window={print(){printCalls++;},addEventListener:(name,handler)=>events[name]=handler};scope.PARENT=p;
vm.runInContext(html.slice(controls,html.indexOf('copyBtn.onclick=',controls)),scope);
const actualBuild=scope.buildBoardReport,actualSpeak=scope.buildSpeakingScript;
scope.buildBoardReport=(data)=>actualBuild(data,now);
scope.buildSpeakingScript=(data)=>actualSpeak(data,now);
elements['meeting-date'].value='2026-11-02';elements.gen.onclick();
assert.match(scope.report.textContent,/MEETING DATE: 2026-11-02/);
assert.match(elements['speech-report'].textContent,/Follow-up required/);
for(const el of [scope.copyBtn,elements.speech,elements['print-report']])assert.equal(el.style.display,'inline-block');
assert.equal(classes.size,0);elements['print-report'].onclick();assert.equal(printCalls,1);assert.ok(classes.has('print-handout'));
events.afterprint();assert.equal(classes.size,0);
await elements.speech.onclick();assert.equal(clipboardText,elements['speech-report'].textContent);
scope.navigator.clipboard.writeText=()=>Promise.reject(new Error('denied'));
await elements.speech.onclick();assert.match(elements.speech.textContent,/Copy failed/);
elements['clear-report'].onclick();assert.equal(scope.report.textContent,'');assert.equal(elements['speech-report'].textContent,'');
for(const el of [scope.report,scope.copyBtn,scope.shareBtn,elements.speech,elements['print-report'],elements['speech-report'],elements['speech-label'],elements['clear-report']])assert.equal(el.style.display,'none');
assert.equal(elements.gen.focused,true);
elements.gen.onclick();assert.equal(elements.speech.textContent,'Copy speaking script');
scope.PARENT=null;classes.add('print-handout');elements.gen.onclick();
for(const el of [scope.copyBtn,scope.shareBtn,elements.speech,elements['print-report'],elements['speech-report'],elements['speech-label']])assert.equal(el.style.display,'none');
assert.equal(elements['speech-report'].textContent,'');assert.equal(classes.size,0);
console.log('PASS: generate, optional meeting date, copy failure, clear, print lifecycle and invalid-data controls');
