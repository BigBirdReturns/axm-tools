"use strict";

async function sha256(text){
  if(globalThis.crypto&&globalThis.crypto.subtle){
    const buffer=await globalThis.crypto.subtle.digest("SHA-256",new TextEncoder().encode(text));
    return [...new Uint8Array(buffer)].map(byte=>byte.toString(16).padStart(2,"0")).join("");
  }
  const rotate=(value,bits)=>(value>>>bits)|(value<<(32-bits));
  const maxWord=2**32;
  const hash=[];
  const constants=[];
  const composites={};
  for(let candidate=2;constants.length<64;candidate++){
    if(!composites[candidate]){
      for(let multiple=candidate*candidate;multiple<400;multiple+=candidate)composites[multiple]=true;
      hash.push((Math.sqrt(candidate)*maxWord)|0);
      constants.push((Math.cbrt(candidate)*maxWord)|0);
    }
  }
  const bytes=[...new TextEncoder().encode(text)];
  const bitLength=bytes.length*8;
  bytes.push(0x80);
  while(bytes.length%64!==56)bytes.push(0);
  for(let shift=56;shift>=0;shift-=8)bytes.push(Math.floor(bitLength/2**shift)&255);
  const initial=hash.slice(0,8);
  for(let offset=0;offset<bytes.length;offset+=64){
    const words=new Uint32Array(64);
    for(let i=0;i<16;i++)words[i]=((bytes[offset+i*4]<<24)|(bytes[offset+i*4+1]<<16)|(bytes[offset+i*4+2]<<8)|bytes[offset+i*4+3])>>>0;
    for(let i=16;i<64;i++){
      const s0=rotate(words[i-15],7)^rotate(words[i-15],18)^(words[i-15]>>>3);
      const s1=rotate(words[i-2],17)^rotate(words[i-2],19)^(words[i-2]>>>10);
      words[i]=(words[i-16]+s0+words[i-7]+s1)>>>0;
    }
    let[a,b,c,d,e,f,g,h]=initial;
    for(let i=0;i<64;i++){
      const s1=rotate(e,6)^rotate(e,11)^rotate(e,25);
      const choice=(e&f)^((~e)&g);
      const temp1=(h+s1+choice+constants[i]+words[i])>>>0;
      const s0=rotate(a,2)^rotate(a,13)^rotate(a,22);
      const majority=(a&b)^(a&c)^(b&c);
      const temp2=(s0+majority)>>>0;
      h=g;g=f;f=e;e=(d+temp1)>>>0;d=c;c=b;b=a;a=(temp1+temp2)>>>0;
    }
    initial[0]=(initial[0]+a)>>>0;initial[1]=(initial[1]+b)>>>0;initial[2]=(initial[2]+c)>>>0;initial[3]=(initial[3]+d)>>>0;
    initial[4]=(initial[4]+e)>>>0;initial[5]=(initial[5]+f)>>>0;initial[6]=(initial[6]+g)>>>0;initial[7]=(initial[7]+h)>>>0;
  }
  return initial.map(value=>value.toString(16).padStart(8,"0")).join("");
}
