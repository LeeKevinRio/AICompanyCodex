(function(root){
 function summarize(results,total,expected,now=Date.now(),referenceDate=null){
  const valid=results.filter(a=>a&&now-a.loadedAt<1800000&&a.planEnabled&&a.forecasts?.some(f=>f.days===5)&&a.asOf&&now-Date.parse(a.asOf+'T00:00:00+08:00')<8*86400000);
  const dates=[...new Set(valid.map(a=>a.asOf))].sort((a,b)=>valid.filter(x=>x.asOf===b).length-valid.filter(x=>x.asOf===a).length||b.localeCompare(a));
  const sample=valid.filter(a=>a.asOf===dates[0]);
  const votes={'偏多':0,'震盪':0,'偏空':0};for(const a of sample){const bias=a.forecasts.find(f=>f.days===5).bias;if(bias in votes)votes[bias]++}
  const count=Object.values(votes).reduce((a,b)=>a+b,0),ready=expected>0&&count>=Math.min(5,expected)&&count/expected>=.8&&(!referenceDate||dates[0]>=referenceDate);
  return {ready,reason:referenceDate&&dates[0]&&dates[0]<referenceDate?'日線日期待同步':null,count,total,expected,date:dates[0],votes,bias:ready?(votes['偏多']/count>=.6?'偏多':votes['偏空']/count>=.6?'偏空':'震盪'):null};
 }
 function latestClose(rows){const valid=rows.filter(q=>/^\d{4}-\d{2}-\d{2}$/.test(q.date)&&Number.isFinite(q.change)),date=valid.map(q=>q.date).sort().at(-1),sample=valid.filter(q=>q.date===date);return {date,rows:sample,change:sample.length?sample.reduce((v,q)=>v+q.change,0)/sample.length:null}}
 root.SectorOutlook={summarize,latestClose};if(typeof module!=='undefined')module.exports=root.SectorOutlook;
})(typeof globalThis!=='undefined'?globalThis:this);
