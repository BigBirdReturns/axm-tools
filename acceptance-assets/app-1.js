function init(){
  let theme="light";try{theme=localStorage.getItem("axm_readiness_theme")||theme}catch(_e){}
  if(theme!=="light"&&theme!=="dark")theme="light";
  state.theme=theme;document.documentElement.dataset.theme=theme;updateThemeIcon();
  document.querySelectorAll(".navbtn").forEach(b=>b.addEventListener("click",()=>go(b.dataset.tab)));
  $("goDataBtn").addEventListener("click",()=>go("data"));
  $("themeBtn").addEventListener("click",toggleTheme);
  $("chooseBtn").addEventListener("click",e=>{e.stopPropagation();$("fileInput").click()});
  $("dropzone").addEventListener("click",e=>{if(e.target.closest("button,input"))return;$("fileInput").click()});
  $("dropzone").addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();$("fileInput").click()}});
  $("fileInput").addEventListener("change",e=>stageFiles([...e.target.files],false));
  for(const ev of ["dragenter","dragover"]){$("dropzone").addEventListener(ev,e=>{e.preventDefault();$("dropzone").classList.add("drag")})}
  for(const ev of ["dragleave","drop"]){$("dropzone").addEventListener(ev,e=>{e.preventDefault();$("dropzone").classList.remove("drag")})}
  $("dropzone").addEventListener("drop",e=>stageFiles([...e.dataTransfer.files],false));
  $("restoreBtn").addEventListener("click",()=>runFiles(makeDemoFiles(),true));
  $("analyzeBtn").addEventListener("click",()=>runFiles(state.files,state.isDemo));
  $("clearBtn").addEventListener("click",clearState);
  $("exportJsonBtn").addEventListener("click",exportJson);
  $("exportHtmlBtn").addEventListener("click",exportHtml);
  runFiles(makeDemoFiles(),true);
}

function go(tab){
  state.tab=tab;
  document.querySelectorAll("[data-panel]").forEach(p=>p.hidden=p.dataset.panel!==tab);
  document.querySelectorAll(".navbtn").forEach(b=>b.setAttribute("aria-current",b.dataset.tab===tab?"page":"false"));
  $("tabTitle").textContent=TITLES[tab][0];$("tabSub").textContent=TITLES[tab][1];window.scrollTo({top:0,behavior:"auto"});
}
function toggleTheme(){state.theme=state.theme==="dark"?"light":"dark";document.documentElement.dataset.theme=state.theme;try{localStorage.setItem("axm_readiness_theme",state.theme)}catch(_e){}updateThemeIcon()}
function updateThemeIcon(){$("themeBtn").textContent=state.theme==="dark"?"☀":"☾"}
function setStatus(message,isError=false){const el=$("statusMsg");el.hidden=!message;el.textContent=message;el.classList.toggle("error",isError)}
function stageFiles(files,isDemo){
  const clean=files.filter(f=>f&&f.name).slice(0,MAX_FILES);const total=clean.reduce((a,f)=>a+f.size,0);
  if(total>MAX_TOTAL_BYTES){setStatus(`Selection is ${formatBytes(total)}. This browser demo caps one batch at ${formatBytes(MAX_TOTAL_BYTES)}; split the batch and retry.`,true);return}
  state.files=clean;state.isDemo=!!isDemo;renderFileList();$("analyzeBtn").disabled=!clean.length;setStatus(clean.length?`${clean.length} surface(s) staged locally. Select Analyze surfaces to recompute every tab.`:"");
}
function renderFileList(){
  $("fileList").hidden=!state.files.length;$("fileRows").innerHTML=state.files.map(f=>`<div class="filerow"><span>${esc(f.name)}</span><span style="color:var(--mut)">${formatBytes(f.size)}</span></div>`).join("");
}
function clearState(){state.files=[];state.results=[];state.findings=[];state.findingNote=null;state.isDemo=false;$("fileInput").value="";renderFileList();setStatus("");$("analyzeBtn").disabled=true;$("exportJsonBtn").disabled=true;$("exportHtmlBtn").disabled=true;renderAll();}

async function runFiles(files,isDemo){
  if(!files.length)return;state.busy=true;state.files=files;state.isDemo=!!isDemo;renderFileList();setBusy(true);setStatus("Analyzing local surfaces…");
  try{const results=[];for(const file of files)results.push(await analyzeFile(file));state.results=results;const built=buildFindings(results);state.findings=built.findings;state.findingNote=built.note;setStatus(isDemo?`Loaded the worked example — ${results.length} built-in surfaces. Everything derives from them.`:`Analyzed ${results.length} file(s). Results updated across every tab.`);$("exportJsonBtn").disabled=false;$("exportHtmlBtn").disabled=false;renderAll();go("finding")}
  catch(err){setStatus("Analysis failed: "+(err&&err.message?err.message:String(err))+". Files were read locally only; nothing left this machine.",true)}
  finally{state.busy=false;setBusy(false)}
}
function setBusy(v){$("analyzeBtn").disabled=v||!state.files.length;$("analyzeBtn").textContent=v?"Analyzing…":"Analyze surfaces"}

async function analyzeFile(file){
  const ext=getExt(file.name);const base={fileName:file.name,extension:ext,sizeBytes:file.size,sha256:"not_computed",analyzedAt:new Date().toISOString()};
  if(file.size>MAX_FILE_BYTES)return {...base,surfaces:[failSurface("oversize_file","file_too_large_for_browser_demo",`File is ${formatBytes(file.size)}; the standalone demo caps one file at ${formatBytes(MAX_FILE_BYTES)}.`,["Split the export, select the relevant sheet/table, or run a larger batch inside a controlled AXM runtime."])]};
  base.sha256=await sha256File(file);
  if(CSV_EXTS.has(ext)){const rows=parseDelimited(await file.text(),ext==="tsv"?"\t":","),picked=chooseHeaderAndRows(rows,stem(file.name)),res=scoreTable(picked.headers,picked.dataRows.length,stem(file.name));res.records=buildRecords(picked.headers,picked.dataRows,picked.headerIndex+2);res.headerRow=picked.headerIndex+1;return {...base,surfaces:[{...res,sheet:null}]}}
  if(XLSX_EXTS.has(ext))return {...base,surfaces:await analyzeXlsx(file)};
  if(JSON_EXTS.has(ext)){
    try{if(ext==="jsonl"){const items=(await file.text()).split(/\r?\n/).filter(x=>x.trim()).map(x=>JSON.parse(x));return {...base,surfaces:[{...detectJsonShape(items),sheet:null}]}}const obj=JSON.parse(await file.text());return {...base,surfaces:[{...detectJsonShape(obj),sheet:null}]}}
    catch(err){return {...base,surfaces:[failSurface("json","malformed_json","JSON parse failed: "+err.message,["Fix the JSON or provide it as a verbatim source document."])]}}
  }
  if(IMG_EXTS.has(ext)){const dims=await imageDimensions(file).catch(()=>null);return {...base,surfaces:[{sheet:null,status:"PASS_WITH_GAPS",surfaceType:"screenshot_or_image",evidenceTierCandidate:"pixel_capture",passesAs:"Opaque rendered-surface evidence candidate",rowsCount:1,columnsDetected:[],canonicalFieldsDetected:[],missingMinimumGroups:[],missingRecommendedFields:["source_system","capture_time","visible_context"],reason:"Image can be hashed and preserved as pixel evidence"+(dims?` (${dims.width}×${dims.height}).`:"."),limitations:["No OCR or semantic truth is claimed at this tier.","It proves which bytes entered intake, not what the pixels mean.","A human-gated annotation layer is required before content claims are made."]}]}}
  if(TEXT_EXTS.has(ext)){const text=await file.text();const lines=text.split(/\r?\n/).filter(x=>x.trim()).length;return {...base,surfaces:[{sheet:null,status:"PASS_WITH_GAPS",surfaceType:"text_or_report",evidenceTierCandidate:"source_record",passesAs:"Verbatim report/log evidence candidate",rowsCount:lines,columnsDetected:[],canonicalFieldsDetected:[],missingMinimumGroups:[],missingRecommendedFields:["claim_mapping","source_record_id"],reason:"Text can be preserved as verbatim source evidence.",limitations:["Needs extraction or human mapping before operational claims can be checked."]}]}}
  if(DOC_EXTS.has(ext)){return {...base,surfaces:[{sheet:null,status:"PASS_WITH_GAPS",surfaceType:"document_capture",evidenceTierCandidate:"opaque_document",passesAs:"Hashed source-document candidate",rowsCount:1,columnsDetected:[],canonicalFieldsDetected:[],missingMinimumGroups:[],missingRecommendedFields:["claim_mapping","source_record_id"],reason:`${ext.toUpperCase()} bytes can be hashed and retained, but this zero-dependency page does not parse the document body.`,limitations:["Export the relevant table to XLSX/CSV/JSON for structured findings.","The document can still serve as a source artifact after human mapping."]}]}}
  if(BINARY_EXPORT_EXTS.has(ext)){return {...base,surfaces:[{sheet:null,status:"PASS_WITH_GAPS",surfaceType:"binary_data_export",evidenceTierCandidate:"opaque_binary_export",passesAs:"Hashed binary-export candidate",rowsCount:1,columnsDetected:[],canonicalFieldsDetected:[],missingMinimumGroups:[],missingRecommendedFields:["readable_table_export"],reason:`${ext.toUpperCase()} is preserved as a hashed surface, but this browser-only harness does not inspect its internal rows.`,limitations:["Export the relevant table or query result to CSV/JSON/XLSX for analysis."]}]}}
  return {...base,surfaces:[failSurface("unknown","unsupported","Unsupported file type: "+(ext||"none"),["Export to CSV, XLSX, JSON, text, PDF, or provide a screenshot/image."])]};
}

function normalizeHeader(s){return String(s??"").trim().toLowerCase().replace(/[^a-z0-9]+/g,"_").replace(/^_+|_+$/g,"")}
