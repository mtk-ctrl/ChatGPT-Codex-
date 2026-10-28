(() => {
 'use strict';
 const base='/ChatGPT-Codex-';
 const pages=new Set(['/','/index.html','/ship28.html','/guide.html','/forecast.html','/about.html','/404.html']);
 if(location.hostname!=='mtk-ctrl.github.io'||!location.pathname.startsWith(base+'/'))return;
 const path=location.pathname.slice(base.length)||'/';if(!pages.has(path))return;
 const params=new URLSearchParams(location.search),isTest=params.get('counter_test')==='1';
 const read=k=>{try{return localStorage.getItem(k);}catch{return null;}};
 const write=(k,v)=>{try{localStorage.setItem(k,v);}catch{}};
 if(params.get('counter_disable')==='1'){write('reset-counter-disabled','1');return;}
 if(params.get('counter_enable')==='1'){write('reset-counter-disabled','0');}
 if(read('reset-counter-disabled')==='1'||navigator.doNotTrack==='1'||navigator.globalPrivacyControl===true)return;
 if(navigator.webdriver===true&&!isTest)return;
 const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
 const newId=()=>crypto.randomUUID();
 let visitor=isTest?null:read('reset-counter-visitor');
 if(!uuid.test(visitor||'')){visitor=newId();if(!isTest)write('reset-counter-visitor',visitor);}
 let session=null;try{session=JSON.parse(isTest?'null':read('reset-counter-session'));}catch{}
 const now=Date.now();if(!session||!uuid.test(session.id||'')||!Number.isFinite(session.lastSeen)||now-session.lastSeen>30*60*1000||now<session.lastSeen)session={id:newId(),lastSeen:now};
 session.lastSeen=now;if(!isTest)write('reset-counter-session',JSON.stringify(session));
 let referrer='';try{const u=new URL(document.referrer);if(u.hostname!==location.hostname)referrer=u.hostname;}catch{}
 const ua=navigator.userAgent||'',device=/ipad|tablet/i.test(ua)?'tablet':/mobile|android|iphone/i.test(ua)?'mobile':'desktop';
 const payload={event_id:newId(),visitor_id:visitor,session_id:session.id,path,referrer_host:referrer,device,is_test:isTest};
 let sent=false;
 const send=()=>{if(sent||document.visibilityState==='hidden'||document.prerendering)return;sent=true;fetch('https://reset-visit-ingest-mtk-ctrls-projects.vercel.app/api/collect',{method:'POST',headers:{'Content-Type':'text/plain;charset=UTF-8'},body:JSON.stringify(payload),mode:'cors',credentials:'omit',keepalive:true}).catch(()=>{});};
 send();if(!sent)document.addEventListener('visibilitychange',send,{once:true});
})();
