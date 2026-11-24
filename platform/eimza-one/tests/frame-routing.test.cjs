const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function frame(host,asset){
 const events=[],notes=[];
 const w={location:{origin:'https://'+host,href:'https://'+host+'/'},frames:[],fetch(){throw Error('local request escaped');},addEventListener(type,fn){if(type==='message')events.push(fn);},postMessage(){}};
 w.parent=w;
 const c=vm.createContext({window:w,URL,URLSearchParams,Response,Request,Event,setTimeout,clearTimeout,setInterval(){},Date,console,
  atob:s=>Buffer.from(s,'base64').toString('binary'),btoa:s=>Buffer.from(s,'binary').toString('base64')});
 w.EimzaNative={arkTransportStatus:s=>notes.push(s)};
 const f={w,c,events,notes};f.load=()=>vm.runInContext(fs.readFileSync('app/src/main/assets/'+asset,'utf8'),c);return f;
}
function connect(parent,child){
 const down={postMessage(data,target){assert.equal(target,child.w.location.origin,'reply must target requesting origin');queueMicrotask(()=>child.events.forEach(fn=>fn({source:up,data,origin:parent.w.location.origin})));}};
 const up={postMessage(data){queueMicrotask(()=>parent.events.forEach(fn=>fn({source:down,data,origin:child.w.location.origin})));}};
 parent.w.frames.push(down);child.w.parent=up;return down;
}
(async()=>{
 const root=frame('enabiz.gov.tr','arksigner-bridge.js'),middle=frame('enabiz.gov.tr','arksigner-bridge.js'),child=frame('enabiz.gov.tr','arksigner-bridge.js');
 connect(root,middle);connect(middle,child);
 const untrusted={postMessage(){throw Error('certificate sent to unrelated iframe');}};root.w.frames.push(untrusted);
 root.load();middle.load();child.load();
 child.w.EimzaNative.accept=(origin,encoded)=>{const task=JSON.parse(Buffer.from(encoded,'base64'));root.w.__eimzaArkResolve(JSON.stringify([{responseCode:'0',transactionUUID:task.transactionUUID}]));};
 let delivered=0;
 child.w.pwsigner={processResponse(text){assert.equal(JSON.parse(text)[0].responseCode,'0');delivered++;},connector:{send(){}}};
 child.w.pwsigner.connector.send(Buffer.from(JSON.stringify({action:'initialize',transactionUUID:'frame-init'})).toString('base64'));
 await new Promise(r=>setImmediate(r));assert.equal(delivered,1,'native reply must survive arriving before nested route registration');
 assert(child.notes.some(n=>n.includes('geri çağrısı teslim edildi: initialize')));
 const a=frame('avukat.uyap.gov.tr','adalet-bridge.js'),b=frame('avukat.uyap.gov.tr','adalet-bridge.js'),d=frame('avukat.uyap.gov.tr','adalet-bridge.js');connect(a,b);connect(b,d);a.w.frames.push(untrusted);a.load();b.load();d.load();
 d.w.EimzaNative.adaletRequest=(id)=>a.w.__eimzaAdaletResolve(id,JSON.stringify({data:{signedData:'test-CMS',txId:'test-tx'},metadata:{}}));
 const reply=await d.w.fetch('http://localhost:5975/api/v1/signature/sign',{method:'POST',body:'{}'});
 assert.equal((await reply.json()).data.txId,'test-tx','Adalet signedData object must stay an object in requesting frame');
 const wrong=frame('avukat.uyap.gov.tr','arksigner-bridge.js');wrong.load();assert.equal(wrong.w.__eimzaArkInstalled,undefined);
 const wrongAdalet=frame('recetem.enabiz.gov.tr','adalet-bridge.js');wrongAdalet.load();assert.equal(wrongAdalet.w.__eimzaAdaletHook,undefined);
 console.log('PASS: nested ArkSigner/Adalet iframe replies, early-reply race, object data preserved, unrelated-frame privacy, portal isolation');
})().catch(e=>{console.error(e);process.exitCode=1});
