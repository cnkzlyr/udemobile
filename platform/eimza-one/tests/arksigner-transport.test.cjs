const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const calls=[], notes=[], intervals=[], events=[];
class Node { appendChild(node) { return node; } insertBefore(node) { return node; } replaceChild(node,old) { return old; } }
const w={Node,location:{origin:'https://recetem.enabiz.gov.tr',href:'https://recetem.enabiz.gov.tr/'},
 addEventListener(type,fn){if(type==='message')events.push(fn);},postMessage(value){this.messages.push(value);},messages:[],
 EimzaNative:{accept(origin,value){calls.push({origin,task:JSON.parse(Buffer.from(value,'base64'))});},arkTransportStatus(text){notes.push(text);}}};
const context=vm.createContext({window:w,URL,Event,atob:s=>Buffer.from(s,'base64').toString('binary'),btoa:s=>Buffer.from(s,'binary').toString('base64'),setTimeout,clearTimeout,setInterval:fn=>intervals.push(fn),console});
const encode=o=>Buffer.from(JSON.stringify(o)).toString('base64');
vm.runInContext(fs.readFileSync('app/src/main/assets/arksigner-bridge.js','utf8'),context);
let boot;
w.bootstrap=rows=>{boot=rows;};
const script={tagName:'SCRIPT',src:'https://local.pwsigner.ark-teknoloji.com:16357/?callback=bootstrap&parameters='+encode({action:'initialize',transactionUUID:'init'}),dispatchEvent(){}};
new Node().appendChild(script);
assert.equal(calls[0].task.action,'initialize');
w.__eimzaArkResolve(JSON.stringify([{responseCode:'0',transactionUUID:'init',nonce:'test'}]));
assert.equal(boot[0].responseCode,'0');
// Exercise transaction processing from the JavaScript shipped in the original ELF.
vm.runInContext('function PWSigner(){}; var pwsigner; var Base64={encode:btoa};',context);
vm.runInContext(fs.readFileSync('app/src/main/assets/arksigner-sdk.js','utf8'),context);
vm.runInContext('pwsigner=new PWSigner(); pwsigner.connector={send:function(){throw Error("original transport must not run")}}; pwsigner.transactions={}; pwsigner.inDebugMode=false;',context);
w.pwsigner=context.pwsigner;
assert.equal(w.pwsigner.connector.send.__eimzaNative,true,'assignment must bind before first poll');
w.pwsigner.connector.send=function(){throw Error('connector initialization replaced native send');};
assert.equal(w.pwsigner.connector.send.__eimzaNative,true,'subsequent send assignment must stay bound');
intervals[0]();
let certs;
context.pwsigner.transactions.certs=function(code,text){certs=JSON.parse(text);assert.equal(code,'0');};
context.pwsigner.connector.send(encode({action:'listSignerCertificatesAsJSON',transactionUUID:'certs'}));
w.__eimzaArkResolve(JSON.stringify([{responseCode:'0',transactionUUID:'certs',certificateHex:'AABB'}]));
assert.equal(certs[0].certificateHex,'AABB');assert.equal(context.pwsigner.transactions.certs,undefined);
// Firefox compatibility: exactly one native request and one reply.
events[0]({source:w,data:{direction:'from-page-script',message:encode({action:'listCardTypeAndSlots',transactionUUID:'firefox'})}});
w.__eimzaArkResolve(JSON.stringify([{responseCode:'0',transactionUUID:'firefox'}]));
assert.equal(w.messages.length,1);assert.equal(w.messages[0].direction,'from-firefox-content-script');
assert.equal(calls.length,3);
const external={tagName:'SCRIPT',src:'https://enabiz.gov.tr/main.js'};
assert.equal(new Node().appendChild(external),external);assert.equal(calls.length,3);
// A replacement connector sends its first request immediately, before any timer.
w.pwsigner.connector={send:function(){throw Error('new connector initial send escaped');}};
w.pwsigner.transactions.early=function(code){assert.equal(code,'0');};
w.pwsigner.connector.send(encode({action:'listCardTypeAndSlots',transactionUUID:'early'}));
assert.equal(calls[3].task.transactionUUID,'early');
w.__eimzaArkResolve(JSON.stringify([{responseCode:'0',transactionUUID:'early'}]));
assert(notes.every(s=>!s.includes('AABB')));
console.log('PASS: ArkSigner bootstrap, real SDK callbacks, synchronous first-request capture, connector replacement, Firefox reply, external script passthrough');
