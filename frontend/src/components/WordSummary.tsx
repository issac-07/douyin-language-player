import { useEffect, useRef, useState } from 'react';
import type { DictionaryResult, SavedWord } from '../types';
import { DictionaryPanel } from './DictionaryPanel';
export function WordSummary({selection,result,error,vocabulary,save,editable = true}: {
 editable?:boolean; selection:{word:string;pinyin:string;nonce:number}|null; result:DictionaryResult|null; error:string;
 vocabulary:SavedWord[]; save:(word:string,status:SavedWord['status'],notes:string)=>Promise<void>;
}) {
 const generation=useRef(0);
 const timer=useRef<ReturnType<typeof setTimeout>|null>(null);
 const [voices,setVoices]=useState<SpeechSynthesisVoice[]>([]);
 const [speaking,setSpeaking]=useState(false);
 const [message,setMessage]=useState('');
 const [saving,setSaving]=useState(false);
 const [savedMessage,setSavedMessage]=useState('');
 useEffect(()=>{
   if (!('speechSynthesis' in window)) return;
   const update=()=>setVoices(window.speechSynthesis.getVoices().filter(v=>v.localService && /^(zh-(cn|tw|sg)|cmn)(-|$)/i.test(v.lang.replace('_','-'))).sort((a,b)=>Number(b.lang.toLowerCase()==='zh-cn')-Number(a.lang.toLowerCase()==='zh-cn')));
   update(); window.speechSynthesis.addEventListener('voiceschanged',update);
   const voicesRefresh=setTimeout(update,1500);
   return ()=>{clearTimeout(voicesRefresh);window.speechSynthesis.removeEventListener('voiceschanged',update);generation.current++;if(timer.current)clearTimeout(timer.current);window.speechSynthesis.cancel();};
 },[]);
 useEffect(()=>{generation.current++;if(timer.current)clearTimeout(timer.current);if ('speechSynthesis' in window) window.speechSynthesis.cancel();setSpeaking(false);setMessage('');setSavedMessage('');},[selection?.word,selection?.nonce]);
 const existing=vocabulary.find(w=>w.word===selection?.word);
 const meaning=result?.translation ? result.translation.text ?? (result.translation.status==='pending'?'Translating…':'Translation unavailable') : result?.entries[0]?.meanings[0] ?? (result?'No exact dictionary entry':'Looking up…');
 const speak=()=>{
   if (!selection || !voices.length) return;
   const token=++generation.current;if(timer.current)clearTimeout(timer.current);window.speechSynthesis.cancel();setMessage('');setSpeaking(true);
   const utterance=new SpeechSynthesisUtterance(selection.word);utterance.voice=voices[0];utterance.lang=voices[0].lang;utterance.rate=.85;
   const finish=()=>{if(token!==generation.current)return false;if(timer.current)clearTimeout(timer.current);setSpeaking(false);return true;};
   utterance.onend=()=>{finish();};
   utterance.onerror=e=>{if(finish() && !['canceled','interrupted'].includes(e.error))setMessage('Pronunciation failed. Please try again.');};
   timer.current=setTimeout(()=>{if(finish()){generation.current++;window.speechSynthesis.cancel();setMessage('Pronunciation timed out. Check the installed Mandarin voice.');}},15000);
   try{window.speechSynthesis.speak(utterance);}catch{if(finish())setMessage('Pronunciation is unavailable in this browser.');}
 };
 if(!selection)return null;
 return <section className="word-summary" aria-label="Selected word" data-testid="selected-word">
 {!selection?<p className="word-prompt">Select a word in the subtitles to see its meaning.</p>:<>
 <div className="word-summary-line"><strong lang="zh" className="summary-hanzi">{selection.word}</strong><div className="summary-meaning"><div><span lang="zh-Latn">{selection.pinyin || result?.entries[0]?.pinyin}</span><button aria-label="Pronounce Chinese word" title={voices.length?'Read with a local Mandarin voice':'Install a Mandarin system voice to enable pronunciation'} disabled={!voices.length || speaking} onClick={speak}>🔊</button></div><p lang={result?.translation?.target_language ?? (result?.translation ? 'vi' : 'en')}>{(error || meaning).normalize('NFC')}</p>{result?.translation && <small>Machine translation</small>}</div><button className="save-star" aria-label={existing?'Word saved':'Save word'} disabled={saving || !!existing} onClick={async()=>{setSaving(true);try{await save(selection.word,'new','');setSavedMessage('Word saved.');}catch(e){setSavedMessage((e as Error).message);}finally{setSaving(false);}}}>{existing?'★':'☆'}</button></div>
 {!voices.length && <small className="voice-note">Pronunciation needs a local Mandarin voice installed on this device.</small>}
 {(message || savedMessage) && <p role="status">{message || savedMessage}</p>}
 <details className="word-more" key={selection.word}><summary>More</summary><DictionaryPanel selection={selection} result={result} error={error} vocabulary={vocabulary} save={save} editable={editable}/></details>
 </>}
 </section>;
}
