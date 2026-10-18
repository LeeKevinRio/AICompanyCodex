(function(root){
 function aggregate(rows,referenceDate,live=[],today=new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Taipei'})){
  const validDay=d=>{if(!/^\d{4}-\d{2}-\d{2}$/.test(d))return false;const n=new Date(d+'T00:00:00Z');return Number.isFinite(n.getTime())&&n.toISOString().slice(0,10)===d&&d<=today};
  const badDate=rows.some(q=>q&&!validDay(q.date));
  const usable=rows.filter(q=>q&&validDay(q.date)&&Number.isFinite(q.change));
  const newest=[referenceDate,...usable.map(q=>q.date)].filter(Boolean).sort().at(-1);
  const selected=usable.filter(q=>q.date===newest),issues=badDate?['來源日期無效／超前']:[];const ids=new Set();
  for(const q of selected){
   if(ids.has(q.id))issues.push('重複成分');ids.add(q.id);
   if(Math.abs(q.change)>12)issues.push('異常漲跌待核對');
   const other=live.find(s=>s.id===q.id&&['active','last_trade','previous_close'].includes(s.status)&&s.quotedAt);
   if(other&&other.quotedAt.slice(0,10)>q.date)issues.push('日期待同步');
   if(other&&other.quotedAt.slice(0,10)===q.date&&Number.isFinite(other.change)&&Math.abs(other.change-q.change)>.05)issues.push('來源漲跌不一致');
  }
  if(!selected.length&&usable.length)issues.push('日期待同步');
  const valid=issues.length?[]:selected;
  return {date:newest,rows:valid,change:valid.length?valid.reduce((v,q)=>v+q.change,0)/valid.length:null,issues:[...new Set(issues)],phase:selected.some(q=>q.phase==='盤中快照')?'盤中快照':selected.some(q=>q.phase==='前收參考')?'前收參考':'收盤資料'};
 }
 function alignAnalysis(a,q){const date=q?.quotedAt?.slice(0,10);if(a&&date&&['last_trade','previous_close'].includes(q.status)&&a.asOf<date)return {...a,planEnabled:false,forecasts:[],alerts:[...(a.alerts||[]),'日線與最新已收盤報價不同日，暫停趨勢與價位，請重新取得資料。']};return a}
 root.DataIntegrity={aggregate,alignAnalysis};if(typeof module!=='undefined')module.exports=root.DataIntegrity;
})(typeof globalThis!=='undefined'?globalThis:this);
