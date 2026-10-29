// Read-only administrator report. Deployed only to a Vercel preview with
// Vercel Authentication; public production must never serve this route.
const backend = 'https://reset-visit-counter.mtk551141.chatgpt.site';
const datePattern = /^\d{4}-\d{2}-\d{2}$/;
function dateValue(s) {
 if (typeof s !== 'string' || !datePattern.test(s)) return null;
 const d = new Date(s + 'T00:00:00Z');
 return Number.isFinite(d.getTime()) && d.toISOString().slice(0,10) === s ? d : null;
}
export default async function handler(req,res) {
 res.setHeader('Cache-Control','private, no-store, max-age=0');
 res.setHeader('X-Robots-Tag','noindex, nofollow');
 res.setHeader('Content-Type','application/json; charset=utf-8');
 // Second barrier, beyond Vercel Authentication: never expose stats on the
 // publicly accessible production collection domain, including future builds.
 if (process.env.VERCEL_ENV !== 'preview') { res.status(404).end(); return; }
 if (req.method !== 'GET') { res.status(405).end(); return; }
 const {from,to,test} = req.query || {};
 const a = dateValue(from), b = dateValue(to);
 if (!a || !b || b < a || b - a > 92 * 86400000 || (test!==undefined && test!=='1')) {
  res.status(400).end(JSON.stringify({error:'invalid_date_range'}));return;
 }
 const token=process.env.COUNTER_STORE_TOKEN;
 if (!token) { res.status(503).end(JSON.stringify({error:'report_unavailable'})); return; }
 const url = new URL('/api/stats',backend);
 url.searchParams.set('from',from); url.searchParams.set('to',to);
 if (test==='1') url.searchParams.set('test','1');
 try {
  const up=await fetch(url,{headers:{'OAI-Sites-Authorization':'Bearer '+token},
    signal:AbortSignal.timeout(8000),redirect:'manual'});
  if (!up.ok) { res.status(502).end(JSON.stringify({error:'upstream_unavailable'})); return; }
  const data=await up.json();
  if (![data.pageviews,data.visitors,data.sessions].every(x=>Number.isSafeInteger(x)&&x>=0)) {
   res.status(502).end(JSON.stringify({error:'unexpected_response'})); return;
  }
  const report={from,to,test:test==='1',pageviews:data.pageviews,
   visitors:data.visitors,sessions:data.sessions,
   daily:Array.isArray(data.daily)?data.daily:[],
   pages:Array.isArray(data.pages)?data.pages:[],
   referrers:Array.isArray(data.referrers)?data.referrers:[]};
  res.status(200).end(JSON.stringify(report));
 } catch {res.status(502).end(JSON.stringify({error:'upstream_unavailable'}));}
}
