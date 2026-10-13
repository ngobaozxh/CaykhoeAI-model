const fs = require('fs');
const path = require('path');
const tf = require('../vendor/tf.min.js');
const root = path.resolve(__dirname, '..');
async function load(folder) {
  const m = JSON.parse(fs.readFileSync(path.join(folder, 'model.json'), 'utf8'));
  const b = fs.readFileSync(path.join(folder, m.weightsManifest[0].paths[0]));
  return tf.loadLayersModel(tf.io.fromMemory({modelTopology:m.modelTopology, weightSpecs:m.weightsManifest.flatMap(g=>g.weights), weightData:b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength)}));
}
(async()=>{
  await tf.setBackend('cpu');
  const full = await load(path.join(root,'model'));
  const quant = await load(path.join(root,'model','quant'));
  const cases=[];
  for (const kind of ['gray','gradient','seeded-noise','leaf-tone']) {
    const pixels=new Float32Array(224*224*3);
    let seed=5243;
    for(let y=0;y<224;y++)for(let x=0;x<224;x++)for(let c=0;c<3;c++) {
      seed=(Math.imul(seed,1664525)+1013904223)>>>0;
      pixels[(y*224+x)*3+c]=kind==='gray'?.5:kind==='gradient'?(x+y)/(2*223):kind==='seeded-noise'?seed/4294967295:Math.min(1,Math.max(0,[.2,.45,.16][c]+.1*Math.sin(x*.1)*Math.cos(y*.08)));
    }
    const input=tf.tensor4d(pixels,[1,224,224,3]);
    const outputs=[];const ms=[];
    for(const model of [full,quant]){
      const t=performance.now(),out=model.predict(input);
      outputs.push(Array.from(await out.data()));ms.push(Math.round(performance.now()-t));out.dispose();
    }
    input.dispose();
    const top=outputs.map(a=>a.indexOf(Math.max(...a)));
    cases.push({kind,top1_full:top[0],top1_candidate:top[1],agreement:top[0]===top[1],max_probability_delta:Math.max(...outputs[0].map((v,i)=>Math.abs(v-outputs[1][i]))),ms_full:ms[0],ms_candidate:ms[1],sums:outputs.map(a=>a.reduce((s,v)=>s+v,0))});
  }
  full.dispose();quant.dispose();
  const result={tfjs:tf.version.tfjs,backend:tf.getBackend(),note:'Synthetic inputs verify execution and drift only. NOT a field accuracy test. Quantized storage decodes to float32; no speed/RAM claim.',cases,remaining_tensors:tf.memory().numTensors};
  fs.writeFileSync(path.join(root,'outputs','model-validation.json'),JSON.stringify(result,null,2));
  console.log(JSON.stringify(result,null,2));
  if(cases.some(c=>c.sums.some(s=>!Number.isFinite(s)||Math.abs(s-1)>.001)))process.exit(1);
})().catch(e=>{console.error(e);process.exit(1);});
