/* Static original map connected to the public browser-local journal. */
(()=>{'use strict';const S=globalThis.SuginamiStore,knownFacts=new Set(SuginamiData.facts.map(x=>x.factId)),knownActions=new Set(SuginamiData.actions.map(x=>x.id));let current,selected,lang='en';
try{lang=new URLSearchParams(location.search).get('lang')||localStorage.getItem('suginami-language')||'en'}catch{}if(lang!=='ja')lang='en';globalThis.__suginamiLocale=lang;
const t=(a,b)=>lang==='ja'?b:a,$=id=>document.getElementById(id);
function status(x,bad=false){$('map-status').textContent=x;$('map-connection').style.background=bad?'#742c2c':'#102f3a';}
function labels(){document.documentElement.lang=lang;$('map-home').textContent=t('Complete project','プロジェクト全体');$('review-link').textContent=t('Claims, actions & evidence','主張・行動・証拠');$('selected-link').textContent=t('Review selected item','選択項目を確認');$('map-export').textContent=t('Export local journal','記録を出力');$('source-disposition').textContent=t('Original author claims. Grades are not independent verification.','原作者の主張。評価は独立検証ではありません。');}
async function refresh(){current=await S.state();globalThis.__suginamiReportIds=current.reported_ids;globalThis.__suginamiApplyReports?.(current.reported_ids);status(t('Saved on this browser. Progress and acceptance are separate.','このブラウザーに保存。進捗と受入は別です。'));return current;}
globalThis.SuginamiSelection=(trigger,payload)=>{
 if(trigger==='locale-toggle'){lang=lang==='ja'?'en':'ja';try{localStorage.setItem('suginami-language',lang)}catch{}labels();}
 if(trigger==='fact-click'&&knownFacts.has(payload?.factId))selected={kind:'claim',id:payload.factId};
 if(trigger==='card-click'&&knownActions.has(payload?.actionId))selected={kind:'action',id:payload.actionId};
 if(selected){$('selected-link').href='../review/#'+selected.kind+'='+encodeURIComponent(selected.id);if(parent!==window)parent.postMessage({type:'suginami-selection',...selected},location.origin);}
};
globalThis.SuginamiJournal={toggle:async(id,callback)=>{try{if(!knownActions.has(id))throw Error('unknown_action');const fresh=await S.state();const result=await S.append({kind:'action-report',action:id,reported:!fresh.reports[id].reported},'browser-local operator');current=result;globalThis.__suginamiReportIds=result.reported_ids;callback(result.reported_ids);status(t('Progress saved locally; not a claim of field acceptance.','進捗をローカル保存。現場受入を意味しません。'));}catch(e){status(t('Write held: ','書込み保留：')+e.message,true);}}};
$('map-export').onclick=async()=>{try{S.download('Suginami-browser-journal.json',await S.exportPacket())}catch(e){status(e.message,true)}};
window.addEventListener('storage',e=>{if(e.key===S.KEY)refresh().catch(x=>status(x.message,true))});
labels();(async()=>{try{await refresh();await import('./assets/index-CfXUNPWr.js');}catch(e){status(t('Map or saved-state error: ','地図・保存状態のエラー：')+e.message,true);}})();
})();
