// 음성·자막 받아쓰기 — 백그라운드 워커
// transformers.js(Whisper)를 별도 스레드에서 실행해 메인 화면이 멈추지 않게 한다.
// 메인 스레드에서 검증된 설정(wasm)을 워커 안에서 그대로 사용한다.

import { pipeline, env } from 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.0.2';

env.allowLocalModels = false;   // 모델은 항상 원격(HuggingFace)에서
env.useBrowserCache = true;     // 한 번 받으면 브라우저 캐시에 저장

let tr = null;     // 파이프라인 캐시
let key = '';      // 현재 로드된 (모델|양자화) 조합

self.onmessage = async (e) => {
  const m = e.data;
  if(m.type !== 'run') return;
  try{
    const k = m.modelId + '|' + m.quant;
    if(!tr || key !== k){
      tr = await pipeline('automatic-speech-recognition', m.modelId, {
        dtype: m.quant ? 'q8' : 'fp32',     // 경량 q8 / 정밀 fp32 (wasm)
        progress_callback: p => self.postMessage({ type:'progress', data:p })
      });
      key = k;
    }
    const opts = { chunk_length_s:30, stride_length_s:5, return_timestamps:true, task:m.task };
    if(m.lang !== 'auto') opts.language = m.lang;
    const out = await tr(m.audio, opts);
    self.postMessage({ type:'done', data:out });
  }catch(err){
    self.postMessage({ type:'error', error:(err && err.message) || String(err) });
  }
};
