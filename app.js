
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const INPUT_SIZE = 224;
  const MODEL_VARIANT = 'quant';
  const MODEL_URL = MODEL_VARIANT === 'quant' ? 'model/quant/model.json' : 'model/model.json';
  const MODEL_CACHE = 'indexeddb://caykhoeai-v6-uint16-kernels-' + MODEL_VARIANT;
  const HISTORY_KEY = 'caykhoeai_history_v1';
  const HISTORY_MAX = 15;
  const DB_NAME = 'caykhoeai-history-v2';
  const cac_lop = ['benh_loet_chanh','cam_bi_xi_mu','cam_khoe_manh','chanh_khoe_manh','chanh_vang_la','lua_bi_nam','lua_binh_thuong','lua_sau_cuon_la','lua_sau_duc_than','mia_gi_sat','mia_khoe_manh','mia_thoi_do','ngo_chay_la','ngo_khoe_manh'];
  const names = {'benh_loet_chanh':'Bệnh loét chanh','cam_bi_xi_mu':'Cam bị xì mủ','cam_khoe_manh':'Cam khỏe mạnh','chanh_khoe_manh':'Chanh khỏe mạnh','chanh_vang_la':'Chanh vàng lá','lua_bi_nam':'Lúa bị nấm','lua_binh_thuong':'Lúa bình thường','lua_sau_cuon_la':'Lúa sâu cuốn lá','lua_sau_duc_than':'Lúa sâu đục thân','mia_gi_sat':'Mía gỉ sắt','mia_khoe_manh':'Mía khỏe mạnh','mia_thoi_do':'Mía thối đỏ','ngo_chay_la':'Ngô cháy lá','ngo_khoe_manh':'Ngô khỏe mạnh'};
  const tips = {all:'Cam: thân cây. Chanh: lá hoặc quả. Lúa: lá hoặc thân. Ngô và mía: lá. Giữ ảnh đủ sáng, rõ nét và ít nền.',cam:'Chụp rõ thân cây và vùng có dấu hiệu xì mủ; thêm một ảnh toàn cây để đối chiếu.',chanh:'Chụp rõ lá hoặc quả có dấu hiệu bất thường, đủ sáng; tránh chụp cả tán cây quá xa.',lua:'Chụp lá hoặc thân có dấu hiệu bất thường. Đối chiếu thêm với tình trạng ruộng.',mia:'Chụp rõ mặt lá có dấu hiệu. Những bệnh cần kiểm tra thân phải đối chiếu thực địa.',ngo:'Chụp rõ lá có dấu hiệu cháy hoặc đốm bệnh, không để lá quá nhỏ trong ảnh.'};
  const chatBox = $('chat-box'), emptyState = $('emptyState'), fileInput = $('fileInput');
  const fileName = $('fileName'), form = $('chatForm'), sendBtn = $('sendBtn');
  const statusBox = $('modelStatus'), statusText = $('modelStatusText'), progressBar = $('modelProgress');
  let mo_hinh = null, thong_tin_benh = {}, busy = false, modelReady = false, selectedFile = null;
  let previewURL = null, db = null, history = [], modelLoading = false, storageWarning = false;
  let historyInitialization = null, clearingHistory = false;
  const FALLBACK_KEY = 'caykhoeai_history_v2_fallback';
  const esc = (s) => String(s || '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const percent = (v) => (100 * Math.max(0, Math.min(1, Number(v) || 0))).toFixed(1) + '%';
  const announce = (text) => { if ($('liveAnnouncement')) $('liveAnnouncement').textContent = text; };
  function setStatus(text, kind) {
    statusText.textContent = text;
    statusBox.classList.remove('error','ready');
    if (kind) statusBox.classList.add(kind);
    $('retryModel').hidden = kind !== 'error';
  }
  async function chon_backend() {
    if (tf.wasm) {
      tf.env().set('WASM_HAS_MULTITHREAD_SUPPORT', false);
      tf.wasm.setWasmPaths(window.__CKAI_WASM_PATHS || 'vendor/');
    }
    for (const backend of ['wasm','webgl','cpu']) {
      try { if (await tf.setBackend(backend)) { await tf.ready(); return backend; } } catch (e) { console.warn('Backend unavailable:', backend); }
    }
    throw new Error('Không có backend AI phù hợp trên trình duyệt này.');
  }
  async function predictAsync(pixels) {
    const input = tf.tensor4d(pixels, [1, INPUT_SIZE, INPUT_SIZE, 3]);
    let output;
    try { output = mo_hinh.predict(input); return Array.from(await output.data()); }
    finally { input.dispose(); if (output) tf.dispose(output); }
  }
  function predictPixels(pixels) {
    return tf.tidy(() => Array.from(mo_hinh.predict(tf.tensor4d(pixels,[1,INPUT_SIZE,INPUT_SIZE,3])).dataSync()));
  }
  async function loadAll() {
    if (modelLoading) return;
    modelLoading = true; modelReady = false; updateSendState();
    progressBar.parentElement.hidden = false;
    setStatus('Đang khởi động mô hình AI…');
    let candidate = null;
    try {
      if (typeof tf === 'undefined') throw new Error('Thiếu thư viện AI.');
      await chon_backend();
      if (window.__CKAI_SINGLE_FILE) {
        thong_tin_benh = JSON.parse(window.__CKAI_KNOWLEDGE);
        candidate = await tf.loadLayersModel(tf.io.fromMemory({modelTopology:window.__CKAI_TOPOLOGY.modelTopology,weightSpecs:window.__CKAI_SPECS,weightData:window.__CKAI_binBuffer()}));
      } else {
        const res = await fetch('dieu_tri.json');
        if (!res.ok) throw new Error('Không đọc được kho kiến thức.');
        thong_tin_benh = await res.json();
        try { candidate = await tf.loadLayersModel(MODEL_CACHE); } catch (e) {  }
        if (!candidate) {
          if (location.protocol === 'file:') throw new Error('Hãy dùng bản một tệp để mở trực tiếp từ máy.');
          setStatus('Đang tải gói AI khoảng 6 MB; ảnh của bạn vẫn ở trên máy.');
          candidate = await tf.loadLayersModel(MODEL_URL,{onProgress:(p)=> {progressBar.style.width = Math.round(p*100)+'%';}});
        }
      }
      if (candidate.inputs[0].shape.slice(1).join(',') !== '224,224,3' || candidate.outputs[0].shape[1] !== cac_lop.length) throw new Error('Mô hình không khớp nhãn nhận diện.');
      if (mo_hinh) mo_hinh.dispose();
      mo_hinh = candidate; candidate = null;
      const warm = await predictAsync(new Float32Array(INPUT_SIZE*INPUT_SIZE*3));
      validatePredictions(warm);
      modelReady = true;
      if (!window.__CKAI_SINGLE_FILE) {
        try { await mo_hinh.save(MODEL_CACHE); } catch (e) { storageWarning = true; }
        try { if (navigator.storage && navigator.storage.persist) await navigator.storage.persist(); } catch (e) {  }
      }
      setStatus('AI sẵn sàng · ' + tf.getBackend().toUpperCase() + ' · phân tích tại máy', 'ready');
      progressBar.parentElement.hidden = true;
      await initHistory();
      chatBox.querySelectorAll('.message.bot').forEach(el => el.remove());
      history.slice().sort((a,b) => (a.created || 0) - (b.created || 0))
        .slice(-HISTORY_MAX).forEach(entry => renderEntry(entry, false));
      announce('Mô hình AI đã sẵn sàng.');
    } catch (e) {
      if (candidate) candidate.dispose();
      if (mo_hinh) { mo_hinh.dispose(); mo_hinh = null; }
      modelReady = false;
      const detail = (location.protocol === 'file:' && !window.__CKAI_SINGLE_FILE)
        ? 'Mở bản cay-khoe-ai-1file.html, không mở index.html trực tiếp.'
        : await diagnoseModelError();
      setStatus('Chưa tải được AI. ' + detail, 'error');
      console.error(e);
    } finally { modelLoading = false; updateSendState(); }
  }
  async function diagnoseModelError() {
    if (location.protocol === 'file:') return 'Tệp mô hình không đọc được từ đĩa. Hãy dùng bản một tệp.';
    const dir = MODEL_URL.split('/').slice(0, -1).join('/');
    let res;
    try {
      res = await fetch(MODEL_URL, { method: 'GET', cache: 'no-store' });
    } catch (e) {
      return 'Không kết nối được để lấy gói AI. Kiểm tra mạng rồi thử lại.';
    }
    if (res.status === 404) return 'Máy chủ không có tệp mô hình (404): ' + MODEL_URL + '. Khi phát hành lên máy chủ tĩnh phải tải lên đủ thư mục ' + dir + '/.';
    if (!res.ok) return 'Máy chủ trả về lỗi ' + res.status + ' khi đọc gói AI.';
    try {
      const spec = await res.json();
      const shards = (spec.weightsManifest || []).reduce((acc, g) => acc.concat(g.paths || []), []);
      for (const name of shards) {
        const r = await fetch(dir + '/' + name, { method: 'GET', cache: 'no-store' });
        if (!r.ok) return 'Thiếu tệp trọng số ' + name + ' (lỗi ' + r.status + '). Phải tải lên đủ thư mục ' + dir + '/, gồm cả tệp .bin.';
      }
    } catch (e) {  }
    return 'Gói AI đọc được nhưng không nạp được. Tải lại trang rồi thử lại.';
  }
  async function decodeImage(file) {
    if (window.createImageBitmap) { try { return await createImageBitmap(file); } catch (e) {  } }
    return new Promise((resolve,reject) => {
      const url = URL.createObjectURL(file), img = new Image();
      img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
      img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('Không đọc được ảnh.')); };
      img.src = url;
    });
  }
  function srcSize(src) { return {w:src.naturalWidth || src.width,h:src.naturalHeight || src.height}; }
  function nearestIndex(n) {
    const s = n / INPUT_SIZE, idx = new Int32Array(INPUT_SIZE); let v = .5 * s;
    for (let i=0;i<INPUT_SIZE;i++) { idx[i] = Math.min(n-1,Math.floor(v)); v += s; }
    return idx;
  }
  function toInputPixels(src) {
    const {w,h} = srcSize(src), MAXPIX = 16000000;
    let fw=w,fh=h;
    if (w*h>MAXPIX) {const s=Math.sqrt(MAXPIX/(w*h));fw=Math.max(1,Math.floor(w*s));fh=Math.max(1,Math.floor(h*s));}
    const c=document.createElement('canvas');c.width=fw;c.height=fh;
    const ctx=c.getContext('2d',{willReadFrequently:true});
    if (!ctx) throw new Error('Không khởi tạo được bộ đọc ảnh.');
    if(w*h>MAXPIX) ctx.imageSmoothingEnabled=false;
    ctx.drawImage(src,0,0,fw,fh);
    const out=new Float32Array(INPUT_SIZE*INPUT_SIZE*3),xs=nearestIndex(fw),ys=nearestIndex(fh);
    let k=0,previous=-1,row=null;
    for(let y=0;y<INPUT_SIZE;y++) {
      if(ys[y]!==previous) {row=ctx.getImageData(0,ys[y],fw,1).data;previous=ys[y];}
      for(let x=0;x<INPUT_SIZE;x++) {const i=xs[x]*4;out[k++]=row[i]/255;out[k++]=row[i+1]/255;out[k++]=row[i+2]/255;}
    }
    c.width=c.height=1;
    return out;
  }
  function thumbnailDataURL(src,maxSide=800) {
    const {w,h}=srcSize(src),s=Math.min(1,maxSide/Math.max(w,h));
    const c=document.createElement('canvas');c.width=Math.max(1,Math.round(w*s));c.height=Math.max(1,Math.round(h*s));
    c.getContext('2d').drawImage(src,0,0,c.width,c.height);
    return c.toDataURL('image/jpeg',.8);
  }
  function imageQuality(pixels,src) {
    let sum=0,sq=0;
    for(let i=0;i<pixels.length;i+=3) {const v=.299*pixels[i]+.587*pixels[i+1]+.114*pixels[i+2];sum+=v;sq+=v*v;}
    const n=pixels.length/3,mean=sum/n,variance=Math.max(0,sq/n-mean*mean),{w,h}=srcSize(src);
    if(variance<.00005) return 'Ảnh gần như một màu, chưa có đủ chi tiết để nhận diện. Hãy chụp rõ vùng có dấu hiệu.';
    if(Math.min(w,h)<100) return 'Ảnh quá nhỏ. Hãy chọn ảnh có cạnh ngắn tối thiểu 100 px.';
    return null;
  }
  function cropOf(label) {return label==='benh_loet_chanh'?'chanh':String(label).split('_')[0];}
  function validatePredictions(preds) {
    if(!Array.isArray(preds)||preds.length!==14||preds.some(v=>!Number.isFinite(v)||v<0||v>1.001)||Math.abs(preds.reduce((a,b)=>a+b,0)-1)>.01) throw new Error('Đầu ra mô hình không hợp lệ.');
  }
  function du_doan_benh(preds,crop='all') {
    validatePredictions(preds);
    const order=preds.map((v,i)=>i).sort((a,b)=>preds[b]-preds[a]);
    const top3=order.slice(0,3).map(i=>({label:cac_lop[i],ten_hien_thi:names[cac_lop[i]],confidence:preds[i]}));
    const label=top3[0].label,confidence=top3[0].confidence;
    const entropy=-preds.reduce((a,p)=>a+(p>0?p*Math.log(p):0),0)/Math.log(14);
    const gap=top3[0].confidence-top3[1].confidence;
    const mismatch=crop!=='all'&&crop!==cropOf(label);
    const uncertain=confidence<.8||gap<.15||entropy>.65||mismatch;
    let reason='Đối chiếu dấu hiệu thực tế. Điểm mô hình không phải tỷ lệ dự đoán đúng.';
    if(mismatch) reason='Kết quả không khớp cây bạn chọn. Chụp lại đúng bộ phận; hệ thống chưa xác nhận được bệnh.';
    else if(confidence<.45||entropy>.8) reason='Mô hình chưa có một gợi ý đủ rõ. Ảnh có thể ngoài phạm vi 14 trạng thái đã học. Hãy chụp lại hoặc nhờ cán bộ kỹ thuật đối chiếu.';
    else if(gap<.15) reason=(cropOf(top3[0].label)===cropOf(top3[1].label)?'Hai trạng thái của cùng loại cây có điểm gần nhau. ':'Hai gợi ý có điểm gần nhau. ')+'Chưa nên kết luận; chụp thêm một ảnh rõ dấu hiệu.';
    else if(uncertain) reason='Điểm mô hình chưa đủ rõ. Chụp thêm góc khác và đối chiếu dấu hiệu trước khi xử lý.';
    const result={label,ten_benh:names[label],confidence,confidence_level:uncertain?'CẦN ĐỐI CHIẾU':'GỢI Ý NỔI BẬT',top3,entropy,gap,mismatch,uncertain,reason,crop,thoi_diem_chan_doan:new Date().toLocaleString('vi-VN')};
    result.text=makeReportText(result);
    return result;
  }
  function makeReportText(r) {
    const info=thong_tin_benh[r.label]||{};
    const lines=['CÂY KHỎE AI — GỢI Ý NHẬN DIỆN',r.thoi_diem_chan_doan||'',r.ten_benh||names[r.label], 'Điểm mô hình: '+percent(r.confidence),'Điểm này không phải tỷ lệ chính xác.',r.reason||'', 'Các gợi ý:'];
    (r.top3||[]).forEach(t=>lines.push((t.ten_hien_thi||names[t.label])+': '+percent(t.confidence)));
    if(!r.mismatch) {if(info.nguyen_nhan)lines.push('Thông tin tham khảo:',info.nguyen_nhan);if(info.dau_hieu)lines.push('Dấu hiệu đối chiếu:',...info.dau_hieu);}
    lines.push('Không tự sử dụng thuốc từ một kết quả ảnh. Xác minh bệnh và tuân thủ đúng nhãn sản phẩm với cán bộ kỹ thuật.');
    return lines.join('\n');
  }
  function legacyHistory() {try {const a=JSON.parse(localStorage.getItem(HISTORY_KEY)||'[]');return Array.isArray(a)?a.filter(e=>e&&typeof e==='object'):[];}catch(e){return [];}}
  async function openHistoryDB() {
    return new Promise((resolve,reject)=>{
      const request=indexedDB.open(DB_NAME,1);
      request.onupgradeneeded=()=>{request.result.createObjectStore('entries',{keyPath:'id'});};
      request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);request.onblocked=()=>reject(new Error('Storage blocked'));
    });
  }
  function dbRead() {return new Promise((resolve,reject)=>{const tx=db.transaction('entries','readonly'),req=tx.objectStore('entries').getAll();req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});}
  function dbPut(entry) {return new Promise((resolve,reject)=>{const tx=db.transaction('entries','readwrite');tx.objectStore('entries').put(entry);tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);});}
  function initHistory() {
    if (historyInitialization) return historyInitialization;
    historyInitialization = (async () => {
      const legacy = legacyHistory().map((entry, i) => ({...entry, id:'legacy-' + i}));
      let fallback = [];
      try {
        const saved = JSON.parse(localStorage.getItem(FALLBACK_KEY) || '[]');
        if (Array.isArray(saved)) fallback = saved.filter(e => e && typeof e.id === 'string' && e.result);
      } catch (e) { storageWarning = true; }
      let persisted = [];
      try { db = await openHistoryDB(); persisted = await dbRead(); }
      catch (e) { if (db) db.close(); db = null; storageWarning = true; }
      const merged = new Map(persisted.map(entry => [entry.id, entry]));
      for (const entry of [...legacy, ...fallback]) {
        if (merged.has(entry.id)) continue;
        merged.set(entry.id, entry);
        if (db) { try { await dbPut(entry); } catch (e) { storageWarning = true; } }
      }
      history = Array.from(merged.values());
      history.sort((a,b) => (a.created || 0) - (b.created || 0))
        .slice(-HISTORY_MAX).forEach(entry => renderEntry(entry, false));
    })();
    return historyInitialization;
  }
  async function saveEntry(entry) {
    await initHistory();
    history.push(entry);
    if(db){try{await dbPut(entry);return;}catch(e){storageWarning=true;}}
    try{localStorage.setItem(FALLBACK_KEY,JSON.stringify(history.slice(-HISTORY_MAX)));}catch(e){storageWarning=true;}
  }
  function renderEntry(entry,scroll=true) {
    emptyState.hidden=true;
    const r=entry.result || {label:entry.label,ten_benh:names[entry.label],confidence:entry.confidence,uncertain:entry.level!=='CAO',top3:[],reason:'Lịch sử cũ không có đầy đủ điểm từng lớp; hãy phân tích lại nếu cần.'};
    const info=r.mismatch?{}:thong_tin_benh[r.label]||{};
    const msg=document.createElement('article');msg.className='message bot';
    const image=typeof entry.img==='string'&&/^data:image\/(jpeg|png|webp);base64,/.test(entry.img)?entry.img:'';
    const symptom=(info.dau_hieu||[]).map(t=>'<li>'+esc(t)+'</li>').join('');
    const top3=(r.top3||[]).map(t=>`<li class="top3-row"><div><span>${esc(t.ten_hien_thi||names[t.label])}</span><span>${percent(t.confidence)}</span></div><div class="probability-track"><div class="probability-fill" style="--score:${Number(t.confidence)||0}"></div></div></li>`).join('');
    msg.innerHTML=`<div class="message-group"><figure class="result-photo">${image?`<img src="${esc(image)}" class="chat-image" alt="Ảnh cây đã phân tích">`:''}<figcaption>${esc(r.thoi_diem_chan_doan||'Lần quan sát trước')}<br>Ảnh được giữ trên thiết bị</figcaption></figure><div class="diagnosis-content"><p class="result-label">Gợi ý nhận diện · Không phải kết luận</p><h2 class="result-heading">${esc(r.ten_benh||'Kết quả cần đối chiếu')}</h2><span class="status-badge ${r.uncertain?'status-warning':'status-model'}">${r.uncertain?'Cần đối chiếu thêm':'Gợi ý có điểm cao nhất'}</span><div class="confidence-wrapper"><div class="confidence-label"><span>Điểm mô hình</span><span class="score">${percent(r.confidence)}</span></div><div class="confidence-track"><div class="confidence-fill" style="--score:${Number(r.confidence)||0}"></div></div><ol class="top3-list" aria-label="Ba gợi ý có điểm cao nhất">${top3}</ol></div><div class="notice ${r.uncertain?'uncertain':''}">${esc(r.reason)}</div>${info.nguyen_nhan?`<section class="knowledge-section"><h3>Hiểu dấu hiệu này</h3><p>${esc(info.nguyen_nhan)}</p></section>`:''}${symptom?`<section class="knowledge-section"><h3>Đối chiếu với cây của bạn</h3><ul class="symptom-list">${symptom}</ul></section>`:''}<section class="knowledge-section"><h3>Bước tiếp theo</h3><ol class="action-list"><li>Chụp thêm vùng có dấu hiệu ở ánh sáng tự nhiên, tránh nền rối.</li><li>So sánh triệu chứng trên nhiều lá hoặc cây lân cận.</li><li>${r.uncertain?'Nhờ cán bộ kỹ thuật xác minh trước khi dùng thuốc.':'Theo dõi thay đổi; xác minh nguyên nhân trước khi xử lý.'}</li></ol></section>${!r.uncertain&&!r.mismatch?`<details class="treatment-panel"><summary>Thông tin xử lý tham khảo</summary><p>Kho kiến thức đi kèm chưa được kiểm chứng theo nhãn từng sản phẩm. Hệ thống không hiển thị liều dùng chung cho nhiều loại thuốc. Hãy xác minh bệnh, ưu tiên chăm sóc và chỉ sử dụng sản phẩm phù hợp theo đúng nhãn.</p>${info.ten_thuoc&&info.ten_thuoc.length?`<p>Tên được ghi trong dữ liệu gốc (chưa xác minh, không phải khuyến nghị sử dụng): ${esc(info.ten_thuoc.join(', '))}.</p>`:''}</details>`:''}${entry.text&&!entry.result?'<details class="treatment-panel"><summary>Xem nội dung lịch sử cũ</summary><pre class="legacy-text">'+esc(entry.text)+'</pre></details>':''}<div class="result-tools"><button type="button" class="pdf-btn">Lưu báo cáo PDF</button><small>${entry.ms?esc(entry.ms)+' ms · ':''}Điểm mô hình không phải tỷ lệ chính xác</small></div></div></div>`;
    msg.querySelector('.pdf-btn').addEventListener('click',()=>exportPDF(entry));
    chatBox.prepend(msg);
    if(scroll){msg.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});announce('Đã phân tích ảnh. '+r.ten_benh+'. '+r.reason);}
    return msg;
  }
  async function exportPDF(entry) {
    const wrapper=document.createElement('div');wrapper.className='report-export';
    const r=entry.result;
    wrapper.innerHTML='<h1>Cây Khỏe AI — Báo cáo quan sát</h1>'+(r?'<h2>'+esc(r.ten_benh)+'</h2>':'')+'<p>'+esc(r?makeReportText(r):entry.text)+'</p>';
    if(entry.img&&/^data:image\/(jpeg|png|webp);base64,/.test(entry.img)){const img=new Image();img.src=entry.img;img.alt='Ảnh cây đã phân tích';wrapper.prepend(img);try{await img.decode();}catch(e){}}
    document.body.appendChild(wrapper);
    try{if(typeof html2pdf==='undefined')throw new Error('Thiếu thư viện PDF.');await html2pdf().set({margin:12,filename:'cay-khoe-ai-quan-sat.pdf',image:{type:'jpeg',quality:.9},html2canvas:{scale:1.5},jsPDF:{unit:'mm',format:'a4',orientation:'portrait'},pagebreak:{mode:['css','legacy']}}).from(wrapper).save();}
    catch(e){showError('Không lưu được PDF. Hãy thử lại; kết quả vẫn được giữ trên màn hình.');}
    finally{wrapper.remove();}
  }
  function showError(text) {emptyState.hidden=true;const el=document.createElement('article');el.className='message error-panel';el.setAttribute('role','alert');el.innerHTML='<h3>Chưa thể phân tích ảnh</h3><p>'+esc(text)+'</p><button type="button" class="secondary-btn">Chọn ảnh khác</button>';el.querySelector('button').onclick=()=>fileInput.click();chatBox.prepend(el);return el;}
  async function diagnose(file) {
    if(!file||busy||clearingHistory||!modelReady)return;
    busy=true;updateSendState();let src=null;
    const thinking=document.createElement('div');thinking.className='thinking';thinking.innerHTML='<span class="spinner" aria-hidden="true"></span>Đang quan sát ảnh trên thiết bị…';thinking.setAttribute('role','status');chatBox.prepend(thinking);
    try{
      src=await decodeImage(file);const t0=performance.now();
      await new Promise(resolve=>requestAnimationFrame(()=>resolve()));
      const pixels=toInputPixels(src),quality=imageQuality(pixels,src);
      if(quality){showError(quality);return;}
      const preds=await predictAsync(pixels),result=du_doan_benh(preds,$('cropSelect').value);
      const entry={id:(crypto.randomUUID?crypto.randomUUID():String(Date.now())+'-'+Math.random()),created:Date.now(),result,label:result.label,confidence:result.confidence,level:result.confidence_level,text:result.text,img:thumbnailDataURL(src),ms:Math.round(performance.now()-t0),modelVariant:MODEL_VARIANT};
      await saveEntry(entry);renderEntry(entry);
      if(storageWarning)announce('Đã phân tích; bộ nhớ không cho phép lưu bền vững. Lưu PDF để giữ kết quả.');
    }catch(e){console.error(e);showError('Không đọc hoặc phân tích được ảnh này. Hãy thử ảnh JPG, PNG hoặc WebP rõ nét.');}
    finally{if(src&&src.close)src.close();thinking.remove();busy=false;updateSendState();}
  }
  function updateSendState(){sendBtn.disabled=!modelReady||busy||!selectedFile;$('cameraBtn').disabled=busy;fileInput.disabled=busy;$('cropSelect').disabled=busy;$('removePhoto').disabled=busy;}
  function resetPhoto(){if(previewURL)URL.revokeObjectURL(previewURL);previewURL=null;selectedFile=null;fileInput.value='';$('cameraInput').value='';$('previewArea').hidden=true;$('dropZone').hidden=false;fileName.textContent='Chọn ảnh hoặc kéo ảnh vào đây';updateSendState();}
  function selectPhoto(file){
    if(!file||busy)return;
    if(!/^image\/(jpeg|png|webp|gif|bmp|avif)$/.test(file.type||'')){showError('Chọn ảnh JPG, PNG hoặc WebP. Đổi ảnh HEIC sang JPG nếu trình duyệt không đọc được.');return;}
    if(file.size>25*1024*1024){showError('Ảnh lớn hơn 25 MB. Hãy giảm kích thước trước khi chọn.');return;}
    if(previewURL)URL.revokeObjectURL(previewURL);
    selectedFile=file;previewURL=URL.createObjectURL(file);$('previewImage').src=previewURL;$('previewArea').hidden=false;$('dropZone').hidden=true;$('previewInfo').textContent=file.name+' · '+(file.size/1024/1024).toFixed(2)+' MB';updateSendState();
  }
  fileInput.addEventListener('change',()=>selectPhoto(fileInput.files[0]));
  $('cameraBtn').addEventListener('click',()=>$('cameraInput').click());
  $('cameraInput').addEventListener('change',()=>selectPhoto($('cameraInput').files[0]));
  $('removePhoto').addEventListener('click',resetPhoto);
  $('cropSelect').addEventListener('change',()=>{$('photoTip').textContent=tips[$('cropSelect').value];});
  $('dropZone').addEventListener('dragover',e=>{e.preventDefault();$('dropZone').classList.add('dragover');});
  $('dropZone').addEventListener('dragleave',()=>$('dropZone').classList.remove('dragover'));
  $('dropZone').addEventListener('drop',e=>{e.preventDefault();$('dropZone').classList.remove('dragover');selectPhoto(e.dataTransfer.files[0]);});
  form.addEventListener('submit',e=>{e.preventDefault();diagnose(selectedFile);});
  $('retryModel').addEventListener('click',loadAll);
  $('clearBtn').addEventListener('click',async()=>{
    if(busy || clearingHistory)return;
    if(!confirm('Xóa toàn bộ lịch sử quan sát trên thiết bị này? Ảnh gốc của bạn không bị xóa.'))return;
    clearingHistory = true; $('clearBtn').disabled = true;
    try{
      await initHistory();
      if (!db) db = await openHistoryDB();
      await new Promise((resolve,reject)=>{const tx=db.transaction('entries','readwrite');tx.objectStore('entries').clear();tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);});
      localStorage.removeItem(HISTORY_KEY);localStorage.removeItem(FALLBACK_KEY);
      history=[];chatBox.querySelectorAll('.message,.thinking').forEach(e=>e.remove());emptyState.hidden=false;announce('Đã xóa lịch sử trên thiết bị.');
    }catch(e){showError('Chưa xóa được toàn bộ lịch sử. Bộ nhớ trình duyệt không cho phép thay đổi.');}
    finally { clearingHistory = false; $('clearBtn').disabled = false; }
  });
  async function offlineReadiness(registration){
    const worker=navigator.serviceWorker.controller||registration.active;
    if(!worker)return;
    const channel=new MessageChannel();
    channel.port1.onmessage=e=>{$('offlineStatus').textContent=e.data.ready?'Đã lưu đủ để dùng ngoại tuyến':'Chưa lưu đủ dữ liệu ngoại tuyến';channel.port1.close();};
    worker.postMessage({type:'CHECK_OFFLINE'},[channel.port2]);
  }
  if(window.__CKAI_SINGLE_FILE){$('offlineStatus').textContent='Bản một tệp · không cần mạng';}
  else if('serviceWorker' in navigator && window.isSecureContext && location.protocol!=='file:'){
    navigator.serviceWorker.register('sw.js').then(async reg=>{await navigator.serviceWorker.ready;await offlineReadiness(reg);navigator.serviceWorker.addEventListener('controllerchange',()=>offlineReadiness(reg));}).catch(()=>{$('offlineStatus').textContent='Ngoại tuyến chưa sẵn sàng';});
  }else{$('offlineStatus').textContent='Dùng HTTPS hoặc bản một tệp để lưu ngoại tuyến';}
  window.__cayKhoeAI={toInputPixels,decodeImage,predictPixels,predictAsync,du_doan_benh,renderEntry,imageQuality,selectPhoto,diagnose,ready:()=>modelReady,version:()=>tf.version.tfjs};
  initHistory().catch(e => { storageWarning = true; console.warn('History unavailable:', e); });
  loadAll();
})();
