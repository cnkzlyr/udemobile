const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
class XHR extends EventTarget {
  get readyState() { return this.state || 0; }
  get status() { return 0; }
  open(method,url) { this.state=1; this.realUrl=url; }
  send(body) { this.realBody=body; }
  abort() { this.realAborted=true; }
  setRequestHeader() { if(!this.realUrl) throw Error('InvalidStateError'); }
  getResponseHeader() { return 'passthrough'; }
  getAllResponseHeaders() { return 'passthrough'; }
}
const requests=[];
let passthrough=0;
const w={XMLHttpRequest:XHR,fetch:()=>{passthrough++;return Promise.resolve('outside');}};
const context=vm.createContext({window:w,Response,Request,Event,setTimeout,clearTimeout,console});
w.EimzaNative={adaletRequest(id,method,url,body){requests.push({id,method,url,body});queueMicrotask(()=>w.__eimzaAdaletResolve(id,JSON.stringify({data:'certificate',metadata:{}})));}};
vm.runInContext(fs.readFileSync('app/src/main/assets/adalet-bridge.js','utf8'),context);
(async()=>{
 const response=await w.fetch('http://localhost:5975/api/v1/signature/getCertificate',{method:'GET',body:'{"certificateId":"a"}'});
 assert.equal((await response.json()).data,'certificate');assert.equal(requests[0].body,'{"certificateId":"a"}');
 await w.fetch(new Request('http://localhost:5975/api/v1/signature/sign',{method:'POST',body:'literal'}));
 assert.equal(requests[1].body,'literal');
 assert.equal(await w.fetch('https://enabiz.gov.tr/page'),'outside');assert.equal(passthrough,1);
 const xhr=new XHR(), events=[];for(const e of ['readystatechange','load','loadend'])xhr.addEventListener(e,()=>events.push(e));
 xhr.open('GET','http://localhost:5975/api/v1/signature/getCertificates');xhr.setRequestHeader('Content-Type','application/json');xhr.responseType='json';
 const done=new Promise(resolve=>xhr.addEventListener('loadend',resolve,{once:true}));xhr.send();await done;
 assert.equal(xhr.readyState,4);assert.equal(xhr.status,200);assert.equal(xhr.response.data,'certificate');assert.deepEqual(events,['readystatechange','readystatechange','load','loadend']);
 assert.match(xhr.getResponseHeader('Content-Type'),/json/);
 xhr.open('GET','https://enabiz.gov.tr/');xhr.send('external');assert.equal(xhr.realBody,'external');assert.equal(xhr.getResponseHeader('x'),'passthrough');
 const aborted=new XHR();aborted.open('GET','http://localhost:5975/client/info');aborted.send();aborted.abort();await new Promise(r=>setImmediate(r));assert.equal(aborted.readyState,0);
 console.log('PASS: Adalet fetch, Request body, XHR readonly properties, headers, events, reuse, abort, nonlocal passthrough');
})().catch(e=>{console.error(e);process.exitCode=1});
