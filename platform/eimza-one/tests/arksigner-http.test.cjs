const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
class XHR extends EventTarget {
 get readyState(){return this.state||0;} get status(){return 0;}
 open(method,url){this.state=1;this.realUrl=url;}send(body){this.realBody=body;}abort(){this.realAborted=true;}
 setRequestHeader(){if(!this.realUrl)throw Error('InvalidStateError');}
 getResponseHeader(){return 'passthrough';}getAllResponseHeaders(){return 'passthrough';}
}
const tasks=[],notes=[];let passthrough=0;
const w={XMLHttpRequest:XHR,location:{origin:'https://recetem.enabiz.gov.tr',href:'https://recetem.enabiz.gov.tr/'},
 addEventListener(){},postMessage(){},fetch(){passthrough++;return Promise.resolve('outside');}};
w.EimzaNative={accept(origin,encoded){const task=JSON.parse(Buffer.from(encoded,'base64'));tasks.push(task);queueMicrotask(()=>w.__eimzaArkResolve(JSON.stringify([{responseCode:'0',transactionUUID:task.transactionUUID}])));},
 arkTransportStatus(text){notes.push(text);},adaletRequest(id){queueMicrotask(()=>w.__eimzaAdaletResolve(id,'{"data":"adalet"}'));}};
const c=vm.createContext({window:w,URL,URLSearchParams,Response,Request,Event,setTimeout,clearTimeout,setInterval(){},console,
 atob:s=>Buffer.from(s,'base64').toString('binary'),btoa:s=>Buffer.from(s,'binary').toString('base64')});
vm.runInContext(fs.readFileSync('app/src/main/assets/arksigner-bridge.js','utf8'),c);
const encoded=tx=>Buffer.from(JSON.stringify({action:'initialize',transactionUUID:tx})).toString('base64');
const url=tx=>'https://local.pwsigner.ark-teknoloji.com:16357/?parameters='+encodeURIComponent(encoded(tx));
(async()=>{
 const unwrap=async response=>JSON.parse((await response.text()).replace(/^\(|\)$/g,''));
 const first=await w.fetch(url('get'));assert.equal((await unwrap(first))[0].transactionUUID,'get');
 const post=await w.fetch(new Request('https://local.api.arksigner.net:16357/',{method:'POST',body:new URLSearchParams({parameters:encoded('post')}).toString()}));
 assert.equal((await unwrap(post))[0].transactionUUID,'post');
 const jsonp=await w.fetch(url('jsonp')+'&callback=site.done');assert.match(await jsonp.text(),/^site\.done\(/);
 const xhr=new XHR();xhr.open('GET',url('xhr'));xhr.setRequestHeader('Accept','application/json');xhr.responseType='json';
 const done=new Promise(resolve=>xhr.addEventListener('loadend',resolve,{once:true}));xhr.send();await done;
 assert.equal(xhr.status,200);assert.equal(xhr.response[0].transactionUUID,'xhr');assert.match(xhr.getResponseHeader('content-type'),/json/);
 const socketV13=new XHR();socketV13.open('POST','https://local.pwsigner.ark-teknoloji.com:16357/');socketV13.responseType='text';
 const socketDone=new Promise(resolve=>socketV13.addEventListener('loadend',resolve,{once:true}));
 socketV13.send(new URLSearchParams({parameters:encoded('socket-v13')}));await socketDone;
 assert.match(socketV13.response,/^\(\[.*\]\)$/,'native SocketV13 service wraps its JSON array in parentheses');
 const socketRows=JSON.parse(socketV13.response.substring(1,socketV13.response.length-1));
 assert.equal(socketRows[0].transactionUUID,'socket-v13','ArkSignerJS 3.0.2 substring/JSON.parse path must receive an array');
 xhr.open('GET','https://enabiz.gov.tr/page');xhr.send('outside');assert.equal(xhr.realBody,'outside');
 assert.equal(await w.fetch('https://enabiz.gov.tr/page?parameters='+encoded('external')),'outside');
 assert.equal(await w.fetch('https://local.api.arksigner.net:443/?parameters='+encoded('port')),'outside');
 assert.equal(passthrough,2);assert.equal(tasks.length,5);
 for(const [tx,body] of [
  ['json',JSON.stringify({parameters:encoded('json')})],
  ['rawtask',JSON.stringify({action:'initialize',transactionUUID:'rawtask'})],
  ['rawbase64',encoded('rawbase64')],
  ['formobject',new URLSearchParams({parameters:encoded('formobject')})]]) {
  const reply=await w.fetch('https://local.api.arksigner.net:16357/',{method:'POST',body});
  assert.equal((await unwrap(reply))[0].transactionUUID,tx);
 }
 const missing=new XHR();missing.open('POST','https://local.api.arksigner.net:16357/');
 const failed=new Promise(resolve=>missing.addEventListener('loadend',resolve,{once:true}));missing.send('{}');await failed;
 assert.equal(missing.status,0);assert(notes.some(n=>n.includes('parameters alanı yok')));assert.equal(tasks.length,9);
 assert.equal(await w.fetch('http://localhost:5975/client/info'),'outside');
 assert.equal(w.__eimzaAdaletHook,undefined,'ArkSigner health page must not install Adalet hook');
 assert(notes.some(t=>t.includes('HTTP')));
 console.log('PASS: ArkSigner 3.0.2 SocketV13 envelope, fetch/XHR/form/JSON/raw-task/Base64 bodies, external passthrough, Adalet coexistence');
})().catch(e=>{console.error(e);process.exitCode=1});
