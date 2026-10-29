import {test} from 'node:test';
import assert from 'node:assert/strict';
import handler from '../counter-ingest/api/stats.mjs';

function response() {
 return {statusCode:0,headers:{},body:'',
  setHeader(k,v){this.headers[k]=v;},
  status(code){this.statusCode=code;return this;},
  end(body=''){this.body=body;return this;}};
}
async function simulate(req,env='preview',fetchFn=()=>{throw Error('not called')}) {
 const prevEnv=process.env.VERCEL_ENV,prevToken=process.env.COUNTER_STORE_TOKEN,prevFetch=globalThis.fetch;
 process.env.VERCEL_ENV=env;process.env.COUNTER_STORE_TOKEN='test-placeholder';
 globalThis.fetch=fetchFn;
 try {const res=response();await handler(req,res);return res;}
 finally {globalThis.fetch=prevFetch;
  if(prevEnv===undefined)delete process.env.VERCEL_ENV;else process.env.VERCEL_ENV=prevEnv;
  if(prevToken===undefined)delete process.env.COUNTER_STORE_TOKEN;else process.env.COUNTER_STORE_TOKEN=prevToken;}
}
test('production is never allowed to read private statistics',async()=>{
 const r=await simulate({method:'GET',query:{from:'2026-10-28',to:'2026-10-29'}},'production');
 assert.equal(r.statusCode,404);
});
test('reject invalid dates, overly broad ranges and other methods',async()=>{
 for(const query of [{from:'2026-02-30',to:'2026-03-01'},{from:'2026-10-30',to:'2026-10-28'},{from:'2026-01-01',to:'2026-10-29'}]){
  const r=await simulate({method:'GET',query});assert.equal(r.statusCode,400);
 }
 const r=await simulate({method:'POST',query:{from:'2026-10-28',to:'2026-10-29'}});
 assert.equal(r.statusCode,405);
});
test('authorized preview returns only aggregates and never the store credential',async()=>{
 let called=false;
 const r=await simulate({method:'GET',query:{from:'2026-10-28',to:'2026-10-29',test:'1'}},'preview',
  async (url,opts)=>{
   called=true;
   assert.ok(url.toString().endsWith('from=2026-10-28&to=2026-10-29&test=1'));
   assert.equal(opts.headers['OAI-Sites-Authorization'],'Bearer test-placeholder');
   return {ok:true,json:async()=>({pageviews:5,visitors:2,sessions:3,daily:[],pages:[],referrers:[],secret:'never-return'})};
  });
 assert.ok(called);assert.equal(r.statusCode,200);
 const report=JSON.parse(r.body);
 assert.deepEqual([report.pageviews,report.visitors,report.sessions],[5,2,3]);
 assert.equal(report.test,true);assert.ok(!('secret' in report));
 assert.ok(!r.body.includes('test-placeholder'));
 assert.equal(r.headers['Cache-Control'],'private, no-store, max-age=0');
});
test('errors from upstream do not become zero counts',async()=>{
 const r=await simulate({method:'GET',query:{from:'2026-10-28',to:'2026-10-29'}},'preview',
  async()=>({ok:false,status:403}));
 assert.equal(r.statusCode,502);assert.equal(JSON.parse(r.body).error,'upstream_unavailable');
});
