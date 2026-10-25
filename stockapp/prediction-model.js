(function(root){
 const taipei=iso=>{const d=new Date(iso);return {date:d.toLocaleDateString('en-CA',{timeZone:'Asia/Taipei'}),time:d.toLocaleTimeString('en-GB',{timeZone:'Asia/Taipei',hour12:false})}};
 function capture(a,recordedAt=new Date().toISOString(),calendar=null){
  if(!a?.planEnabled||!a.bars?.length)return [];
  if(calendar){const next=root.CalendarModel.nextDates(a.asOf,1,calendar),created=taipei(recordedAt);if(!next||next[0]<created.date||(next[0]===created.date&&created.time>='09:00:00'))return [];}
  const b=a.bars.findLast(b=>b.date===a.asOf);if(!b||!(b.close>0))return [];
  return (a.forecasts||[]).filter(f=>[3,5].includes(f.days)&&['偏多','偏空','震盪'].includes(f.bias)).map(f=>({key:`stock:${a.id}:${a.asOf}:${f.days}:${a.model}`,kind:'stock',id:a.id,exchange:a.exchange,asOf:a.asOf,days:f.days,bias:f.bias,baseClose:b.close,recordedAt,model:a.model,adjusted:a.adjusted===true,evidence:{score:a.technical?.score,sampleCount:f.sampleCount,reasons:[...(a.technical?.reasons||[])]},members:null}));
 }
 function evaluate(record,bars,calendar=null,events=[]){
  const anchor=bars.find(b=>b.date===record.asOf);if(!anchor)return {status:'缺少基準日，需補歷史',return:null};
  if(!(anchor.close>0)||Math.abs(anchor.close/record.baseClose-1)>.001)return {status:'來源基準變更待核對',return:null};
  let future=[...new Map(bars.filter(b=>b.date>record.asOf).map(b=>[b.date,b])).values()].sort((a,b)=>a.date.localeCompare(b.date));
  const expected=calendar?root.CalendarModel.nextDates(record.asOf,record.days,calendar):null;
  if(calendar&&!expected)return {status:'交易日曆涵蓋不足',return:null};
  const created=taipei(record.recordedAt);
  if((expected||future.map(b=>b.date)).some(date=>date<created.date||(date===created.date&&created.time>='09:00:00')))return {status:'建立過晚，不納入',return:null};
  if(expected){const matched=expected.map(date=>future.find(b=>b.date===date)).filter(Boolean);if(matched.length<record.days)return {status:bars.at(-1)?.date>=expected.at(-1)?'缺少預期交易日日線':`等待到期 ${matched.length}/${record.days}`,expectedEndDate:expected.at(-1),return:null};future=matched;}
  if(future.length<record.days)return {status:`等待到期 ${future.length}/${record.days}`,return:null};
  const window=future.slice(0,record.days);if(events.some(e=>e.date>record.asOf&&e.date<=window.at(-1).date))return {status:'期間除權息，待還原核對',return:null};let previous=record.baseClose;
  for(const b of window){if(!(b.close>0)||Math.abs(b.close/previous-1)>.3||String(b.note||'').includes('**'))return {status:'價格尺度異常待核對',return:null};previous=b.close}
  const value=(window.at(-1).close/record.baseClose-1)*100,bias=value>.5?'偏多':value<-.5?'偏空':'震盪';
  return {status:'已到期',return:value,realized:bias,hit:bias===record.bias,endDate:window.at(-1).date};
 }
 function validRecord(r){if(!r||typeof r.key!=='string'||![3,5].includes(r.days)||!['偏多','偏空','震盪'].includes(r.bias)||!/^\d{4}-\d{2}-\d{2}$/.test(r.asOf)||!Number.isFinite(Date.parse(r.recordedAt))||typeof r.model!=='string')return false;if(r.kind==='stock')return /^[0-9]{4,6}[A-Z]?$/.test(r.id)&&typeof r.id==='string'&&['tse','otc'].includes(r.exchange)&&Number.isFinite(r.baseClose)&&r.baseClose>0;if(r.kind==='sector')return typeof r.id==='string'&&Array.isArray(r.members)&&r.members.length>0&&r.members.length<=12&&r.members.every(m=>m.kind==='stock'&&validRecord(m))&&new Set(r.members.map(m=>m.id)).size===r.members.length;return false}
 function statistics(evaluated){
  const groups=new Map();
  for(const {r,outcome:o} of evaluated){
   const key=JSON.stringify([r.kind,r.days,r.model]);
   if(!groups.has(key))groups.set(key,{kind:r.kind,days:r.days,model:r.model,total:0,done:0,hits:0,upHits:0,downHits:0,flatHits:0,pending:0,excluded:0,returns:[]});
   const g=groups.get(key);g.total++;
   if(o.status==='已到期'&&Number.isFinite(o.return)&&['偏多','偏空','震盪'].includes(o.realized)&&typeof o.hit==='boolean'){
    g.done++;g.hits+=o.hit?1:0;g.upHits+=o.realized==='偏多'?1:0;g.downHits+=o.realized==='偏空'?1:0;g.flatHits+=o.realized==='震盪'?1:0;g.returns.push(o.return);
   }else if(/^等待|^待取得|^交易日曆待取得/.test(o.status))g.pending++;
   else g.excluded++;
  }
  return [...groups.values()].map(g=>({...g,misses:g.done-g.hits,hitRate:g.done?g.hits/g.done*100:null,alwaysUpRate:g.done?g.upHits/g.done*100:null,alwaysDownRate:g.done?g.downHits/g.done*100:null,constantRate:g.done?Math.max(g.upHits,g.downHits,g.flatHits)/g.done*100:null}));
 }
 root.PredictionModel={capture,evaluate,validRecord,statistics};if(typeof module!=='undefined')module.exports=root.PredictionModel;
})(typeof globalThis!=='undefined'?globalThis:this);
