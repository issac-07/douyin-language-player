import { useEffect, useState } from 'react';
import { api } from '../services/api';
import type { TranslationModel } from '../types';

export function TranslationModelSelector({value,onChange}:{value:TranslationModel;onChange:(value:TranslationModel)=>void}) {
 const [models,setModels]=useState<{id:TranslationModel;label:string;available:boolean}[]>([]);
 const [error,setError]=useState('');
 useEffect(()=>{let alive=true;api.translationModels().then(result=>{if(alive)setModels(result);}).catch(cause=>{if(alive)setError(cause.message);});return()=>{alive=false;};},[]);
 return <div className="translation-model-control"><label htmlFor="translation-model">Translation model</label><select id="translation-model" value={value} disabled={!models.length} onChange={event=>onChange(event.target.value as TranslationModel)}>{models.length?models.map(model=><option key={model.id} value={model.id} disabled={!model.available}>{model.label}{model.available?'':' · not installed'}</option>):<option value={value}>Loading models…</option>}</select><span className="model-selection-help">Changes translation only</span>{error && <span role="alert">{error}</span>}</div>;
}
