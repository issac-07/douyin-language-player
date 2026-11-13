import { useEffect, useRef, useState } from 'react';
import type { SavedWord } from '../types';
type Status=SavedWord['status'];
export function QuickWordActions({word,existing,save,remove}:{
 word:string;existing?:SavedWord;save:(word:string,status:Status,notes:string)=>Promise<void>;remove:(id:string)=>Promise<void>;
}) {
 const [status,setStatus]=useState<Status|null>(existing?.status??null);
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 const removed=useRef<SavedWord|null>(null),lock=useRef(false);
 useEffect(()=>{if(existing)setStatus(existing.status);},[existing?.status]);
 const saved=!!existing && status===existing.status;
 const toggle=async()=>{
  if(lock.current || !status)return;
  lock.current=true;setBusy(true);setError('');
  try {
   if(saved){await remove(existing.id);removed.current=existing;}
   else {await save(word,status,existing?.notes??removed.current?.notes??'');removed.current=null;}
  }catch(cause){setError((cause as Error).message);}
  finally{lock.current=false;setBusy(false);}
 };
 return <div className="quick-word-actions"><div className="quick-word-row">
  <div className="quick-word-status" role="group" aria-label="Word learning status">
   {(['new','learning','known'] as const).map(value=><button type="button" key={value} disabled={busy} aria-pressed={status===value} onClick={()=>setStatus(value)}>{value[0].toUpperCase()+value.slice(1)}</button>)}
  </div>
  <button type="button" className={`word-save ${saved?'is-saved':''}`} aria-label={saved?'Unsave word':existing?'Save changes':'Save word'} aria-pressed={saved} title={saved?'Click to remove from vocabulary':'Save to vocabulary'} disabled={!status || busy} onClick={()=>void toggle()}>{saved?'Saved':'Save'}</button>
 </div>{error && <p role="alert">{error}</p>}</div>;
}
