import { useEffect, useRef, useState } from 'react';
import type { DictionaryResult, SavedWord } from '../types';
import { QuickWordActions } from './QuickWordActions';
import { DictionaryPanel } from './DictionaryPanel';
export function WordSummary({selection,result,error,vocabulary,save,remove,editable = true}: {
 editable?:boolean; selection:{word:string;pinyin:string;nonce:number}|null; result:DictionaryResult|null; error:string;
 remove:(id:string)=>Promise<void>; vocabulary:SavedWord[]; save:(word:string,status:SavedWord['status'],notes:string)=>Promise<void>;
}) {
 const generation=useRef(0);
 const timer=useRef<ReturnType<typeof setTimeout>|null>(null);
 const [speaking,setSpeaking]=useState(false);
 const [message,setMessage]=useState('');
 useEffect(()=>()=>{generation.current++;if(timer.current)clearTimeout(timer.current);window.speechSynthesis?.cancel();},[]);
 useEffect(()=>{generation.current++;if(timer.current)clearTimeout(timer.current);window.speechSynthesis?.cancel();setSpeaking(false);setMessage('');},[selection?.word,selection?.nonce]);
 const existing=vocabulary.find(w=>w.word===selection?.word);
 const meaning=result?.translation ? result.translation.text ?? (result.translation.status==='pending'?'Translating…':'Translation unavailable') : result?.entries[0]?.meanings[0] ?? (result?'No exact dictionary entry':'Looking up…');
 const speak=async()=>{
   if (!selection || speaking) return;
   const token=++generation.current;
   if(timer.current)clearTimeout(timer.current);
   window.speechSynthesis?.cancel();setMessage('');setSpeaking(true);
   const findVoice=()=>window.speechSynthesis?.getVoices().find(v=>v.lang.replace('_','-').toLowerCase()==='zh-cn' && /晓晓|xiaoxiao/i.test(v.name) && (!v.localService || /online/i.test(v.name)));
   let voice=findVoice();
   for(let attempt=0;!voice && attempt<15;attempt++){
     await new Promise(resolve=>setTimeout(resolve,100));
     if(token!==generation.current)return;
     voice=findVoice();
   }
   if(!voice){setSpeaking(false);setMessage('Microsoft Xiaoxiao Online is not available to this page. Open the player in Edge and try again.');return;}
   const finish=()=>{if(token!==generation.current)return false;if(timer.current)clearTimeout(timer.current);setSpeaking(false);return true;};
   const utterance=new SpeechSynthesisUtterance(selection.word);utterance.voice=voice;utterance.lang=voice.lang;utterance.rate=.85;
   utterance.onend=()=>{finish();};
   utterance.onerror=e=>{if(finish() && !['canceled','interrupted'].includes(e.error))setMessage('Pronunciation failed. Please try again.');};
   timer.current=setTimeout(()=>{if(finish()){generation.current++;window.speechSynthesis.cancel();setMessage('Pronunciation timed out. Check the selected voice or connection.');}},15000);
   try{window.speechSynthesis.speak(utterance);}catch{if(finish())setMessage('Pronunciation is unavailable in this browser.');}
 };
 if(!selection)return null;
 return <section className="word-summary" aria-label="Selected word" data-testid="selected-word">
 {!selection?<p className="word-prompt">Select a word in the subtitles to see its meaning.</p>:<>
 <div className="word-summary-line"><strong lang="zh" className="summary-hanzi">{selection.word}</strong><div className="summary-meaning"><div><span lang="zh-Latn">{selection.pinyin || result?.entries[0]?.pinyin}</span><button aria-label="Pronounce Chinese word" title="Microsoft Xiaoxiao Online (Natural)" disabled={speaking} onClick={()=>void speak()}>🔊</button></div><p lang={result?.translation?.target_language ?? (result?.translation ? 'vi' : 'en')}>{(error || meaning).normalize('NFC')}</p>{result?.translation && <small>Machine translation</small>}</div></div>
 {message && <p role="alert">{message}</p>}
 {editable && <QuickWordActions key={`actions:${selection.word}`} word={selection.word} existing={existing} save={save} remove={remove}/>}
 <details className="word-more" key={selection.word}><summary>More</summary><DictionaryPanel selection={selection} result={result} error={error} vocabulary={vocabulary} save={save} editable={editable}/></details>
 </>}
 </section>;
}
