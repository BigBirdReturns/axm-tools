'use strict';
// Test instrumentation for the ordinary Node network APIs used by this source set.
const fs=require('node:fs');
const attempts=[];
function deny(){attempts.push('network API invocation');throw Error('SCHISM recipient test denies network APIs');}
for(const name of ['node:http','node:https']){const m=require(name);m.request=deny;m.get=deny;}
const net=require('node:net');net.connect=deny;net.createConnection=deny;net.Socket.prototype.connect=deny;
require('node:tls').connect=deny;globalThis.fetch=deny;
process.once('exit',()=>{if(process.env.SCHISM_NETWORK_LOG)fs.writeFileSync(process.env.SCHISM_NETWORK_LOG,JSON.stringify({attempts:attempts.length}));});
