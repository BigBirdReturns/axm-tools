'use strict';
const $=id=>document.getElementById(id);
function buildPrompt(){
 const model=$('model').value,route=$('route').value;
 const requested=$('benchmark').value.trim().slice(0,160)||'the benchmark I choose after the first canary';
 $('route-note').textContent=route==='native'?'Keep the native tools, environment, scorer and deadlines. The temporary endpoint is local; no benchmark grade is inferred by the adapter.':route==='offline'?'Only independent, offline requests qualify for batch replay. Freeze the request file and use its original scorer.':'A small canary establishes load/generation behavior, never a benchmark score.';
 $('total-params').textContent=model.endsWith('Pro-RL')?'1.02T':'309B';
 $('active-params').textContent=model.endsWith('Pro-RL')?'42B':'15B';
 const text=`Run an inspectable ONE-GPU experiment for ${model} on my local Linux/WSL2 NVIDIA machine. Use my existing runtime and checkpoint; do not change ODS or stop existing jobs.

Read the kit at https://bigbirdreturns.github.io/axm-tools/mimo-one-gpu/v1/README.md and inspect the source/manifest. Download only the small test kit linked at https://bigbirdreturns.github.io/axm-tools/mimo-one-gpu/ into a new isolated working directory. No model weights, Docker image, Python package or other software may be acquired without separate approval. Verify the kit SHA-256 manifest before running it. The source is a test candidate, not evidence that MiMo already runs on one GPU.

Work from the extracted kit's v1 directory. First run: python3 one_gpu.py inspect --out hardware-private.json. If required tools are missing, report that and stop. Inspect which GPU is actually idle, actual available host RAM and CPU headroom, a complete existing ${model} checkpoint, its exact 40-hex upstream revision, and an existing compatible vLLM Docker image. The publisher names vllm/vllm-openai:mimov25-cu129, but an image tag or generic offload flag does not establish MiMo TP=1 support.

Populate settings.json from observations, not the example RAM figures. Preserve a host reserve of at least 32 GiB where available and cap CPU at no more than half the logical CPUs. Select exactly one GPU. Use a conservative bounded load timeout. Set context to the actual protocol requirement; never shrink a benchmark's context or output budget to make it fit. Run python3 one_gpu.py plan settings.json --out plan-private.json. Show me the exact plan, source identity, memory blockers/warnings and command before asking to load. A BLOCKED plan stays blocked. No swap workaround, second GPU, model substitution, quantization change, expert pruning or remote fallback.

After explicit approval, perform one load/generation canary with the selected model ID in its separately prepared canary request. Use python3 one_gpu.py run plan-private.json canary.jsonl --out runs/canary-001 --approve-load. The runner hashes the full checkpoint, probes exactly one CUDA device, disables container networking, caps RAM/swap/CPU, and stops its own container on failure or deadline. Preserve all failures and outputs; do not silently repair/retry or call the canary a score.

Requested next mode: ${route}. Benchmark: ${requested}.
For independent offline requests, freeze harness/dataset/scorer/config and exact request-file SHA-256 in protocol.json. Run the original requests with --kind benchmark --protocol protocol.json, then apply the original scorer. For interactive, tool-using, logprob or timed benchmarks, use python3 one_gpu.py serve plan-private.json --out runs/native-001 --approve-load and configure the EXISTING native harness with connection-private.json after health returns 200. Keep the temporary API key in local files/environment, not chat or shared reports. The bridge preserves JSON and streaming, never retries, and supports only its advertised endpoints. Keep native deadlines and evaluation environments intact. Missing harness, incompatible endpoint or restricted evaluation data means NOT RUN / ADAPTER REQUIRED, not an approximate substitute.

Compare each benchmark against the same checkpoint/quantization and native protocol on the reference setup, keeping numerical and quality differences visible. Report actual one-card observation, host RAM, full artifact identity, context, scored sample denominator, native score if available, load/hash/run times, memory use and any failures. A header fit is not a native fit. A completed response is not score parity. Do not claim an Artificial Analysis composite from a few examples. Create runs/native-001/STOP when the native trial ends. Review and reduce the receipt before sharing; never upload prompts, model state, GPU UUIDs, paths, tokens or benchmark answer keys automatically.`;
 $('prompt').value=text;return text;
}
async function copy(){const value=buildPrompt();try{await navigator.clipboard.writeText(value);$('copy-status').textContent='Copied. Paste into your existing local coding agent.';}catch{$('prompt').focus();$('prompt').select();$('copy-status').textContent='Clipboard access denied. The handoff is selected for manual copying.';$('prompt').scrollIntoView({block:'center',behavior:'auto'});}}
for(const id of ['model','route','benchmark'])$(id).addEventListener('input',buildPrompt);
$('copy').addEventListener('click',copy);$('copy-secondary').addEventListener('click',copy);buildPrompt();

$('save-prompt').addEventListener('click',()=>{
 const blob=new Blob([buildPrompt()+'\n'],{type:'text/plain;charset=utf-8'});
 const url=URL.createObjectURL(blob);const a=document.createElement('a');
 a.href=url;a.download='mimo-one-gpu-agent-brief.txt';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
const allowedFiles=new Set(Array.from(document.querySelectorAll('[data-file]'),b=>b.dataset.file));
let sourceRequest=0;
async function showSource(file){
 if(!allowedFiles.has(file))return;
 const request=++sourceRequest;
 document.querySelectorAll('[data-file]').forEach(b=>{const selected=b.dataset.file===file;b.classList.toggle('active',selected);b.setAttribute('aria-pressed',String(selected));});
 $('source-name').textContent=file;$('source-raw').href=file;$('source-code').textContent='Reading the published source…';
 $('source-status').textContent='Loading a static file from this site.';
 try {
  const response=await fetch(file,{credentials:'omit',redirect:'error',cache:'no-store'});
  if(!response.ok)throw Error('HTTP '+response.status);
  const text=await response.text();if(text.length>250000)throw Error('Source preview exceeds the size limit');
  if(request!==sourceRequest)return;
  $('source-code').textContent=text;$('source-code').scrollTop=0;$('source-code').scrollLeft=0;
  $('source-status').textContent='Read-only preview · '+text.split('\n').length+' lines · no code executed';
 }catch(error){if(request!==sourceRequest)return;$('source-code').textContent='Source preview unavailable. Use Open raw or the complete kit to inspect this file.';$('source-status').textContent='Read failed: '+error.message;}
}
for(const b of document.querySelectorAll('[data-file]'))b.addEventListener('click',()=>showSource(b.dataset.file));
if('IntersectionObserver' in window){
 const observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)){showSource('v1/README.md');observer.disconnect();}},{rootMargin:'120px'});observer.observe($('source'));
}else{showSource('v1/README.md');}
