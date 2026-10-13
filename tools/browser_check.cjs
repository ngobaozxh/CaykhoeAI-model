
const fs=require('fs'),path=require('path'),{spawn}=require('child_process');
const root=path.resolve(__dirname,'..'),out=path.join(root,'outputs');
const edge='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const port=9237;
const delay=ms=>new Promise(r=>setTimeout(r,ms));
const report={tests:[],exceptions:[]};
const runDir=fs.mkdtempSync(path.join(out,'browser-run-'));
const downloadPath=path.join(runDir,'downloads');
fs.mkdirSync(downloadPath);
report.freshProfile=true;
let browser,ws,id=0;const pending=new Map();
function send(method,params={}){return new Promise((resolve,reject)=>{const n=++id;const timer=setTimeout(()=>{pending.delete(n);reject(new Error('CDP timeout '+method));},90000);pending.set(n,{resolve,reject,timer});ws.send(JSON.stringify({id:n,method,params}));});}
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw new Error(r.exceptionDetails.text+' '+JSON.stringify(r.exceptionDetails.exception));return r.result.value;}
async function waitFor(expression,timeout=90000){const start=Date.now();while(Date.now()-start<timeout){try{if(await evaluate(expression))return;}catch(e){}await delay(150);}throw new Error('Timed out: '+expression);}
async function screenshot(name){const r=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(out,name),Buffer.from(r.data,'base64'));}
function check(name,value){report.tests.push({name,passed:!!value});if(!value)throw new Error('Failed: '+name);}
(async()=>{
  browser=spawn(edge,['--headless=new','--disable-gpu','--no-first-run','--disable-extensions','--remote-debugging-port='+port,'--user-data-dir='+path.join(runDir,'profile'),'about:blank'],{stdio:'ignore'});
  let pages;
  for(let n=0;n<100;n++){try{pages=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();if(pages.some(p=>p.type==='page'))break;}catch(e){}await delay(100);}
  if(!pages)throw new Error('Browser CDP unavailable');
  ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
  await new Promise((r,j)=>{ws.addEventListener('open',r,{once:true});ws.addEventListener('error',j,{once:true});});
  ws.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(new Error(JSON.stringify(m.error))):p.resolve(m.result);}if(m.method==='Runtime.exceptionThrown')report.exceptions.push(m.params.exceptionDetails);});
  await send('Page.enable');await send('Runtime.enable');await send('Network.enable');
  await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  await send('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false});
  const fileURL=new URL('file:///'+path.join(out,'cay-khoe-ai-1file.html').replace(/\\/g,'/')).href;
  await send('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});
  await send('Page.navigate',{url:fileURL});
  await waitFor('window.__cayKhoeAI && window.__cayKhoeAI.ready()');
  check('single-file model initializes with network disabled',true);
  report.runtime=await evaluate('({tf:tf.version.tfjs,backend:tf.getBackend(),status:document.getElementById("modelStatusText").textContent})');
  check('desktop has no horizontal overflow',await evaluate('document.documentElement.scrollWidth<=innerWidth'));
  await screenshot('desktop-preview.png');
  const rules=await evaluate(`(()=>{const api=window.__cayKhoeAI;let p=Array(14).fill(0);p[5]=.5;p[7]=.48;p[6]=.02;const close=api.du_doan_benh(p);p=Array(14).fill(0);p[1]=.99;p[2]=.01;const mismatch=api.du_doan_benh(p,'lua');return {close:close.uncertain,mismatch:mismatch.mismatch,notAccuracy:document.body.textContent.includes('tỷ lệ chính xác')};})()`);
  check('close predictions trigger caution',rules.close);check('crop mismatch triggers caution',rules.mismatch);
  const inferred=await evaluate(`(async()=>{const t=performance.now(),p=await window.__cayKhoeAI.predictAsync(new Float32Array(224*224*3).fill(.5));return {classes:p.length,sum:p.reduce((a,b)=>a+b,0),ms:Math.round(performance.now()-t)};})()`);
  check('real model produces 14 valid probabilities',inferred.classes===14&&Math.abs(inferred.sum-1)<.001);report.inference=inferred;
  const tensors=await evaluate('(async()=>{const before=tf.memory().numTensors;for(let i=0;i<5;i++)await __cayKhoeAI.predictAsync(new Float32Array(224*224*3).fill(.5));return {before,after:tf.memory().numTensors};})()');
  check('repeated inference does not leak tensors',tensors.before===tensors.after);report.tensors=tensors;
  check('nearly blank image rejected',await evaluate(`!!window.__cayKhoeAI.imageQuality(new Float32Array(224*224*3).fill(.5),{width:224,height:224})`));
  await evaluate(`(async()=>{const c=document.createElement('canvas');c.width=c.height=300;const x=c.getContext('2d');for(let y=0;y<300;y+=12)for(let k=0;k<300;k+=12){x.fillStyle='rgb('+Math.round(60+k*.35)+','+Math.round(90+y*.35)+',45)';x.fillRect(k,y,12,12);}const blob=await new Promise(r=>c.toBlob(r,'image/png'));const f=new File([blob],'browser-test-pattern.png',{type:'image/png'});window.__cayKhoeAI.selectPhoto(f);await window.__cayKhoeAI.diagnose(f);})()`);
  check('actual upload renders result',await evaluate('!!document.querySelector(".message.bot .result-heading")'));
  check('structured result includes top three',await evaluate('document.querySelector(".message.bot").querySelectorAll(".top3-row").length===3'));
  check('no unvalidated dose shown in new result',await evaluate('!document.querySelector(".message.bot").textContent.includes("ml cho bình")'));
  await evaluate('scrollTo(0,document.querySelector(".message.bot").offsetTop-20)');
  await screenshot('result-preview.png');
  await send('Emulation.setDeviceMetricsOverride',{width:360,height:820,deviceScaleFactor:1,mobile:true});
  await evaluate('scrollTo(0,0)');await screenshot('mobile-preview.png');
  check('360px mobile has no horizontal overflow',await evaluate('document.documentElement.scrollWidth<=innerWidth'));
  await evaluate('scrollTo(0,document.querySelector(".message.bot").offsetTop-10)');await screenshot('mobile-result.png');
  await send('Page.reload');await waitFor('window.__cayKhoeAI && window.__cayKhoeAI.ready() && document.querySelector(".message.bot")');
  check('single-file history restored after reload',true);
  await send('Browser.setDownloadBehavior',{behavior:'allow',downloadPath,eventsEnabled:true});
  await evaluate('document.querySelector(".pdf-btn").click()');
  await waitFor('!document.querySelector(".report-export")');
  let pdf;
  for(let n=0;n<80;n++){pdf=fs.readdirSync(downloadPath).find(f=>f.endsWith('.pdf'));if(pdf)break;await delay(100);}
  const pdfBytes=pdf?fs.readFileSync(path.join(downloadPath,pdf)):Buffer.alloc(0);
  check('new report PDF has valid file header',pdfBytes.length>1000&&pdfBytes.subarray(0,5).toString()==='%PDF-');
  report.pdfBytes=pdfBytes.length;
  await evaluate(`(async()=>{const db=await new Promise((r,j)=>{const q=indexedDB.open('caykhoeai-history-v2',1);q.onsuccess=()=>r(q.result);q.onerror=()=>j(q.error);});const entries=await new Promise((r,j)=>{const q=db.transaction('entries').objectStore('entries').getAll();q.onsuccess=()=>r(q.result);q.onerror=()=>j(q.error);});db.close();localStorage.setItem('caykhoeai_history_v2_fallback',JSON.stringify([{...entries[0],id:'fallback-recovery-test'}]));})()`);
  const earlyError=await send('Page.addScriptToEvaluateOnNewDocument',{source:`addEventListener('DOMContentLoaded',()=>{window.__cayKhoeAI.selectPhoto(new File(['bad'],'unsupported.txt',{type:'text/plain'}));},{once:true});`});
  await send('Page.reload');await waitFor('window.__cayKhoeAI && __cayKhoeAI.ready() && document.querySelectorAll(".message.bot").length===2');
  check('early invalid file does not suppress history restore',await evaluate('!!document.querySelector(".error-panel")'));
  check('healthy IndexedDB merges fallback without duplicate entries',await evaluate('document.querySelectorAll(".message.bot").length===2'));
  await send('Page.removeScriptToEvaluateOnNewDocument',{identifier:earlyError.identifier});
  const earlyClear=await send('Page.addScriptToEvaluateOnNewDocument',{source:`window.confirm=()=>true;addEventListener('DOMContentLoaded',()=>document.getElementById('clearBtn').click(),{once:true});`});
  await send('Page.reload');await waitFor('window.__cayKhoeAI && __cayKhoeAI.ready() && !document.getElementById("clearBtn").disabled && !document.querySelector(".message.bot")');
  check('startup history clear waits for persistent storage',await evaluate(`(async()=>{const db=await new Promise(r=>{const q=indexedDB.open('caykhoeai-history-v2',1);q.onsuccess=()=>r(q.result);});const count=await new Promise(r=>{const q=db.transaction('entries').objectStore('entries').count();q.onsuccess=()=>r(q.result);});db.close();return count===0&&!localStorage.getItem('caykhoeai_history_v2_fallback')&&!document.querySelector('.message.bot');})()`));
  await send('Page.removeScriptToEvaluateOnNewDocument',{identifier:earlyClear.identifier});
  await send('Network.emulateNetworkConditions',{offline:false,latency:0,downloadThroughput:-1,uploadThroughput:-1});
  await send('Page.navigate',{url:'http://127.0.0.1:8765/index.html'});
  await waitFor('window.__cayKhoeAI && window.__cayKhoeAI.ready()');
  await waitFor('document.getElementById("offlineStatus").textContent.includes("Đã lưu đủ")');
  check('PWA precache explicitly reports complete',true);
  await send('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});
  await send('Page.reload');await waitFor('window.__cayKhoeAI && window.__cayKhoeAI.ready()');
  check('PWA reload initializes while offline',true);
  const pwa=await evaluate('(async()=>{const a=await __cayKhoeAI.predictAsync(new Float32Array(224*224*3).fill(.5));return a.length===14;})()');
  check('PWA inference works while offline',pwa);
  check('no uncaught JS exceptions',report.exceptions.length===0);
  report.ok=true;
})().catch(e=>{report.ok=false;report.error=e.stack;console.error(e);}).finally(()=>{
  fs.writeFileSync(path.join(out,'browser-validation.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
  if(ws)ws.close();if(browser)browser.kill();setTimeout(()=>process.exit(report.ok?0:1),200);
});
