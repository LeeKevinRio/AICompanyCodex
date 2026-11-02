(function(root){
 function groupIds(holdings,watch,group){return [...new Set((group==='watch'?watch:holdings).map(x=>x.id))]}
 function select(id,a,records,calendar,now=new Date().toISOString()){
  const instant=new Date(now),today=instant.toLocaleDateString('en-CA',{timeZone:'Asia/Taipei'}),time=instant.toLocaleTimeString('en-GB',{timeZone:'Asia/Taipei',hour12:false});
  const validDay=d=>typeof d==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(d)&&d<=today;
  const saved=records.filter(r=>r.kind==='stock'&&r.id===id&&validDay(r.asOf)&&[3,5].includes(r.days)&&['偏多','偏空','震盪'].includes(r.bias)&&Number.isFinite(Date.parse(r.recordedAt))&&Date.parse(r.recordedAt)<=instant.getTime());
  const analysis=a&&a.id===id&&validDay(a.asOf)?a:null;
  const base=[...saved.map(r=>r.asOf),...(analysis?[analysis.asOf]:[])].sort().at(-1)||null;
  const version=m=>Number(String(m||'').match(/v(\d+)/)?.[1]||0);
  const signals=[3,5].map(days=>{
   const current=analysis?.planEnabled&&analysis.asOf===base?analysis.forecasts?.find(f=>f.days===days&&['偏多','偏空','震盪'].includes(f.bias)):null;
   const choices=saved.filter(r=>r.asOf===base&&r.days===days).map(r=>({...r,saved:true}));
   if(current)choices.push({...current,asOf:base,model:analysis.model,saved:false});
   choices.sort((x,y)=>version(y.model)-version(x.model)||(Number(y.model===analysis?.model)-Number(x.model===analysis?.model))||Number(y.saved)-Number(x.saved)||String(y.recordedAt||'').localeCompare(x.recordedAt||''));
   // Once a model is chosen its first published signal wins over a changing analysis preview.
   let pick=choices[0];if(pick)pick=choices.find(r=>r.saved&&r.model===pick.model)||pick;
   if(!pick)return {days,bias:null,status:'待取得有效預測',endDate:null};
   const dates=root.CalendarModel?.nextDates(base,days,calendar),endDate=dates?.at(-1)||null;
   const late=pick.saved&&dates&&Date.parse(pick.recordedAt)>=Date.parse(dates[0]+'T09:00:00+08:00');
   const ended=!!pick.outcome||endDate&&(endDate<today||endDate===today&&time>='14:30:00');
   return {...pick,days,endDate,status:late?'建立過晚，不納入':!endDate?'交易日曆待確認':ended?'已到期／待核對':pick.saved?'已封存':'分析預覽 · 未封存',active:!!endDate&&!ended&&!late};
  });
  return {id,asOf:base,signals,warning:analysis?.planEnabled===false?'分析條件未齊；已封存初判僅供核對':base&&base<today?'較早日線基準，請核對日期':''};
 }
 root.ForecastOverview={groupIds,select};if(typeof module!=='undefined')module.exports=root.ForecastOverview;
})(typeof globalThis!=='undefined'?globalThis:this);

function forecastOverviewPanel(ids){return `<article class="card forecast-overview"><div class="row"><div><span class="eyebrow">NEXT 3–5 TRADING DAYS</span><h2>未來趨勢 · ${journalGroup==='watch'?'觀察股':'庫存股'}</h2></div><button id="forecast-refresh">${allAnalysesRunning?'更新中…':'更新追蹤分析'}</button></div><p class="small muted">3／5個交易日方向；已封存初判優先，非保證漲跌。點股票可看下方核對紀錄。</p>${ids.length?`<div class="table-wrap"><table><thead><tr><th>股票／基準日</th><th>3交易日</th><th>5交易日</th></tr></thead><tbody>${ids.map(id=>{const row=ForecastOverview.select(id,analysisCache.get(id),predictionRecords,marketContext?.calendar),holding=holdings.some(h=>h.id===id),watch=watchStocks.some(s=>s.id===id);return `<tr class="${journalStockId===id?'forecast-selected':''}"><td><button data-journal-stock="${id}" aria-pressed="${journalStockId===id}">${escape(trackedName(id))} <small>${id}</small></button><small>${holding&&watch?'庫存＋觀察':holding?'庫存':'觀察'} · 基準 ${escape(row.asOf||'待取得')}</small>${row.warning?`<small class="negative">${escape(row.warning)}</small>`:''}${analysisErrors.get(id)?`<small class="negative">${escape(analysisErrors.get(id))}</small>`:''}</td>${row.signals.map(f=>`<td><strong class="forecast-bias ${f.active?f.bias==='偏多'?'positive':f.bias==='偏空'?'negative':'':'muted'}">${f.bias?escape(f.bias):analysisPending.has(id)?'分析中…':'待分析'}</strong><small>${f.endDate?'至 '+escape(f.endDate):'到期日待確認'} · ${escape(f.model?.match(/v\d+/)?.[0]||'—')}</small><small>${escape(f.status)}</small></td>`).join('')}</tr>`}).join('')}</tbody></table></div>`:`<div class="empty">${journalGroup==='watch'?'尚無觀察股。從上方輸入代碼或名稱加入，不需要設定庫存。':'尚無庫存股。可到「我的庫存」新增，或切換「觀察股」追蹤。'}</div>`}</article>`}
