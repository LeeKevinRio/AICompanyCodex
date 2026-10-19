(function(root){
 function build(holdings,stocks,analyses,now=Date.now()){
  const items=[];const add=(id,priority,title,reason)=>items.push({id,priority,title,reason});
  const total=holdings.reduce((n,h)=>n+h.cost*h.shares,0);
  for(const h of holdings){
   const s=stocks.find(s=>s.id===h.id),a=analyses.get(h.id),name=s?.name||h.id;
   if(!s||!Number.isFinite(s.price)||s.price<=0||!['active','last_trade','previous_close'].includes(s.status))add(h.id,0,name,'行情尚未有效，損益與交易價位需待核對');
   if(!a)add(h.id,1,name,'尚未取得分析資料');
   else {
    const quoteDate=s?.quotedAt?.slice(0,10);
    if(a.pipelineVersion!=='calendar-actions-v3'||!Number.isFinite(a.loadedAt)||a.loadedAt>now||now-a.loadedAt>=1800000)add(h.id,1,name,'分析已過期或版本更新，需重新取得');
    else if(quoteDate&&['last_trade','previous_close'].includes(s.status)&&a.asOf<quoteDate)add(h.id,0,name,'分析日線落後收盤行情，情境與價位暫停');
    else if(!a.planEnabled)add(h.id,1,name,'分析條件未通過，請查看個股限制與來源說明');
    const dates=new Set(a.nextSessions||[]);
    for(const event of a.corporateActions||[])if(dates.has(event.date))add(h.id,0,name,`${event.date} ${event.kind||'公司行動'}，跨事件價位需重新核對`);
   }
   if(total>0&&h.cost*h.shares/total>=.4)add(h.id,2,name,`占投入成本 ${(h.cost*h.shares/total*100).toFixed(1)}%，單一持股集中（提示門檻40%）`);
  }
  return items.sort((a,b)=>a.priority-b.priority||a.id.localeCompare(b.id));
 }
 root.PortfolioAttention={build};if(typeof module!=='undefined')module.exports=root.PortfolioAttention;
})(typeof globalThis!=='undefined'?globalThis:this);
