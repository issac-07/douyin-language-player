import { useEffect, useState } from 'react';
import { api } from '../services/api';
import type { DictionaryResult, SavedWord, WordToken } from '../types';
import { VocabularyPanel } from './DictionaryPanel';
import { WordSummary } from './WordSummary';
export function StandaloneVocabulary(){
 const [words,setWords]=useState<SavedWord[]>([]);
 const [selection,setSelection]=useState<{word:string;pinyin:string;nonce:number}|null>(null);
 const [dictionary,setDictionary]=useState<DictionaryResult|null>(null);
 const [error,setError]=useState('');
 useEffect(()=>{let alive=true;api.vocabulary().then(v=>{if(alive)setWords(v);}).catch(e=>{if(alive)setError(e.message);});return()=>{alive=false;};},[]);
 useEffect(()=>{if(!selection)return;const c=new AbortController();setDictionary(null);api.dictionary(selection.word,c.signal).then(v=>{if(!c.signal.aborted)setDictionary(v);}).catch(e=>{if(!c.signal.aborted)setError(e.message);});return()=>c.abort();},[selection?.nonce]);
 const save=async(word:string,status:SavedWord['status'],notes:string)=>{const result=await api.saveWord(word,status,notes);setWords(old=>[result,...old.filter(w=>w.id!==result.id)]);};
 return <section className="vocabulary-drawer"><h2>Saved words</h2>{error&&<p role="alert">{error}</p>}{selection&&<WordSummary selection={selection} result={dictionary} error={error} vocabulary={words} save={save} remove={async id=>{await api.deleteWord(id);setWords(old=>old.filter(w=>w.id!==id));}}/>}<VocabularyPanel words={words} save={save} remove={async id=>{await api.deleteWord(id);setWords(old=>old.filter(w=>w.id!==id));}} onWord={(token:WordToken)=>setSelection({word:token.text,pinyin:token.pinyin,nonce:Date.now()})}/></section>;
}
