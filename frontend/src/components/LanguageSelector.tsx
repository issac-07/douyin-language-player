function LanguageFlag({language}:{language:'en'|'vi'}) {
 return (  <svg className="language-switch-flag" viewBox="0 0 28 20" width="22" height="16" aria-hidden="true" focusable="false">
   {language==='vi'?<><rect width="28" height="20" fill="#da251d"/><path fill="#ffdf00" d="m14 4 1.5 4.2H20L16.4 11l1.4 4.5-3.8-2.7-3.8 2.7 1.4-4.5L8 8.2h4.5Z"/></>:<><rect width="28" height="20" fill="#012169"/><path d="m0 0 28 20M28 0 0 20" stroke="white" strokeWidth="5"/><path d="m0 0 28 20M28 0 0 20" stroke="#c8102e" strokeWidth="2"/><path d="M14 0v20M0 10h28" stroke="white" strokeWidth="8"/><path d="M14 0v20M0 10h28" stroke="#c8102e" strokeWidth="4"/></>}
  </svg>);
}

export function LanguageSelector({language,onChange}:{language:'en'|'vi';onChange:(language:'en'|'vi')=>void}) {
 return <div className="language-controls"><div className="language-switch" data-language={language} role="group" aria-label="Translation language">
  <span className="language-switch-indicator" aria-hidden="true"/>
  {(['en','vi'] as const).map(value=><button key={value} type="button" aria-pressed={language===value} aria-label={value==='en'?'English':'Tiếng Việt'} onClick={()=>onChange(value)}><LanguageFlag language={value}/><span>{value==='en'?'English':'Tiếng Việt'}</span></button>)}
 </div></div>;
}
