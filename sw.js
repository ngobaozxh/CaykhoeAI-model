
const PREFIX = 'caykhoeai-';
const CACHE = PREFIX + 'v9-selfhosted-fonts';
const FONTS = ['fonts/fraunces-300_600-normal-vi.woff2','fonts/fraunces-300_600-normal-lext.woff2','fonts/fraunces-300_600-italic-vi.woff2','fonts/fraunces-300_600-italic-lext.woff2','fonts/literata-300_700-normal-vi.woff2','fonts/literata-300_700-normal-lext.woff2','fonts/be-vietnam-pro-300-normal-vi.woff2','fonts/be-vietnam-pro-300-normal-lext.woff2','fonts/be-vietnam-pro-400-normal-vi.woff2','fonts/be-vietnam-pro-400-normal-lext.woff2','fonts/be-vietnam-pro-500-normal-vi.woff2','fonts/be-vietnam-pro-500-normal-lext.woff2','fonts/be-vietnam-pro-600-normal-vi.woff2','fonts/be-vietnam-pro-600-normal-lext.woff2'];
const FILES = ['./','index.html','app.js','dieu_tri.json','manifest.webmanifest','vendor/tf.min.js','vendor/tf-backend-wasm.min.js','vendor/tfjs-backend-wasm.wasm','vendor/tfjs-backend-wasm-simd.wasm','vendor/tfjs-backend-wasm-threaded-simd.wasm','vendor/html2pdf.bundle.min.js','model/quant/model.json','model/quant/group1-shard1of1.bin','img/icon-64.png','img/icon-192.png','img/icon-512.png',...FONTS];
self.addEventListener('install',event=>{
  event.waitUntil((async()=>{const cache=await caches.open(CACHE);await cache.addAll(FILES);await self.skipWaiting();})());
});
self.addEventListener('activate',event=>{
  event.waitUntil((async()=>{
    const keys=await caches.keys();
    await Promise.all(keys.filter(k=>k.startsWith(PREFIX)&&k!==CACHE).map(k=>caches.delete(k)));
    await self.clients.claim();
  })());
});
self.addEventListener('message',event=>{
  if(event.data && event.data.type==='CHECK_OFFLINE')event.waitUntil((async()=>{
    const cache=await caches.open(CACHE),hits=await Promise.all(FILES.map(f=>cache.match(new URL(f,self.registration.scope).href)));
    if(event.ports[0])event.ports[0].postMessage({ready:hits.every(Boolean),version:CACHE});
  })());
});
self.addEventListener('fetch',event=>{
  if(event.request.method!=='GET')return;
  const url=new URL(event.request.url);
  if(url.origin!==self.location.origin||!url.href.startsWith(self.registration.scope))return;
  event.respondWith((async()=>{
    const cache=await caches.open(CACHE);
    const hit=await cache.match(event.request,{ignoreSearch:true});
    if(hit)return hit;
    try{return await fetch(event.request);}catch(e){
      if(event.request.mode==='navigate'){const index=await cache.match(new URL('index.html',self.registration.scope).href);if(index)return index;}
      return new Response('Offline: this resource has not been saved.',{status:503,headers:{'Content-Type':'text/plain;charset=utf-8'}});
    }
  })());
});
