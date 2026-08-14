(async()=>{
  const expectedLength=161772;
  const expectedSha="7811477be6347efbdcdb83de022f9d5796845a46d4b634a1433dc196cc9292dc";
  const fail=(message)=>{
    document.body.innerHTML=`<main style="max-width:760px;margin:10vh auto;padding:24px;font:16px/1.55 system-ui;color:#ede8dc"><h1 style="font-size:32px">Manzanita Works could not start</h1><p>${message}</p><p><a style="color:#d97745" href="./">Reload</a></p></main>`;
  };
  try{
    const payload=window.__MW_PAYLOAD||"";
    if(payload.length!==expectedLength) throw new Error(`payload length ${payload.length}; expected ${expectedLength}`);
    const binary=atob(payload);
    const bytes=Uint8Array.from(binary,c=>c.charCodeAt(0));
    const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
    const html=await new Response(stream).text();
    const digest=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(html)))).map(b=>b.toString(16).padStart(2,"0")).join("");
    if(digest!==expectedSha) throw new Error("decoded document failed SHA-256 verification");
    if(!/^<!doctype html>/i.test(html)) throw new Error("decoded document failed identity check");
    document.open();document.write(html);document.close();
  }catch(error){console.error(error);fail(String(error.message||error));}
})();
