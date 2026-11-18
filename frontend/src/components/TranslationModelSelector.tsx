import { useEffect, useState } from 'react';
import { api, type TranslationMemory } from '../services/api';
import type { TranslationModel } from '../types';

export function TranslationModelSelector({value,onChange,onResume}:{value:TranslationModel;onChange:(value:TranslationModel)=>void;onResume:()=>void}) {
 const [models,setModels]=useState<{id:TranslationModel;label:string;available:boolean}[]>([]);
 const [memory,setMemory]=useState<TranslationMemory|null>(null);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 useEffect(()=>{
  let alive=true;
  api.translationModels().then(result=>{if(alive)setModels(result);}).catch(cause=>{if(alive)setError(cause.message);});
  const poll=()=>api.translationMemory().then(result=>{if(alive)setMemory(result);}).catch(cause=>{if(alive)setError(cause.message);});
  void poll();const timer=setInterval(()=>void poll(),2000);
  return()=>{alive=false;clearInterval(timer);};
 },[]);
 const changeMemory=async()=>{
  setBusy(true);setError('');
  try {
   const resume=memory?.paused;
   const result=await (resume?api.resumeTranslationMemory():api.releaseTranslationMemory());
   setMemory(result);
   if(resume&&!result.paused)onResume();
  }catch(cause){setError((cause as Error).message);}finally{setBusy(false);}
 };
 return <div className="translation-model-control"><label htmlFor="translation-model">Translation model</label><select id="translation-model" value={value} disabled={!models.length} onChange={event=>onChange(event.target.value as TranslationModel)}>{models.length?models.map(model=><option key={model.id} value={model.id} disabled={!model.available}>{model.label}{model.available?'':' · not installed'}</option>):<option value={value}>Loading models…</option>}</select><span className="model-selection-help">Changes translation only</span>
 <button type="button" className="secondary-button" disabled={busy||!memory||memory.release_pending} onClick={()=>void changeMemory()}>{memory?.release_pending?'Releasing memory…':memory?.paused?'Resume translation':'Free model memory'}</button>
 <span className="translation-memory-status" role="status">{memory?.release_pending?'Waiting for the current sentence to finish.':memory?.paused?'Translation paused · saved translations remain available.':memory?.model_loaded?`Model in memory · auto-release after ${Math.round(memory.idle_seconds/60)}m idle`:'Model unloaded · loads when needed.'}</span>
 {error && <span role="alert">{error}</span>}</div>;
}
