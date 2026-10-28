const allowedOrigin='https://mtk-ctrl.github.io';
const storeUrl='https://reset-visit-counter.mtk551141.chatgpt.site';
const paths=new Set(['/','/index.html','/about.html','/ship28.html','/guide.html','/forecast.html','/404.html']);
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export default async function handler(req,res){
 res.setHeader('Cache-Control','no-store');res.setHeader('X-Robots-Tag','noindex');
 if(req.headers.origin!==allowedOrigin){res.status(403).end();return;}
 res.setHeader('Access-Control-Allow-Origin',allowedOrigin);res.setHeader('Vary','Origin');
 res.setHeader('Access-Control-Allow-Methods','POST, OPTIONS');res.setHeader('Access-Control-Allow-Headers','Content-Type');
 if(req.method==='OPTIONS'){res.status(204).end();return;}
 if(req.method!=='POST'){res.status(405).end();return;}
 let v;try{const body=typeof req.body==='string'?req.body:JSON.stringify(req.body);if(!body||body.length>2048){res.status(413).end();return;}v=JSON.parse(body);}catch{res.status(400).end();return;}
 if(!v||!paths.has(v.path)||![v.event_id,v.visitor_id,v.session_id].every(x=>typeof x==='string'&&uuid.test(x))){res.status(400).end();return;}
 if(v.is_test!==true&&/bot|spider|crawl|headless|playwright|puppeteer/i.test(req.headers['user-agent']||'')){res.status(204).end();return;}
 if(!process.env.COUNTER_STORE_TOKEN){console.error('counter_missing_store_token');res.status(503).end();return;}
 const clean={event_id:v.event_id,visitor_id:v.visitor_id,session_id:v.session_id,path:v.path,referrer_host:typeof v.referrer_host==='string'&&/^[a-z0-9.-]{0,150}$/i.test(v.referrer_host)?v.referrer_host:'',device:['mobile','tablet','desktop'].includes(v.device)?v.device:'unknown',is_test:v.is_test===true};
 try{const upstream=await fetch(storeUrl+'/api/collect',{method:'POST',redirect:'manual',signal:AbortSignal.timeout(8000),headers:{'Content-Type':'application/json','OAI-Sites-Authorization':'Bearer '+process.env.COUNTER_STORE_TOKEN},body:JSON.stringify(clean)});if(upstream.status!==202){console.error('counter_store_status',upstream.status);res.status(503).end();return;}res.status(204).end();}catch{console.error('counter_store_unavailable');res.status(503).end();}
}
