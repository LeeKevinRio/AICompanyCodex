(function(root){
 function capture(a,now,calendar){
  const research=a?.candidateResearch;
  if(!research||!calendar||!Number.isFinite(Date.parse(research.frozenAt))||Date.parse(now)<Date.parse(research.frozenAt))return [];
  const probe=root.PredictionModel.capture({...a,forecasts:[{days:3,bias:'震盪'}]},now,calendar)[0];
  if(!probe)return [];
  return research.signals.filter(s=>s.asOf===a.asOf).map(s=>({...probe,key:`candidate:${a.id}:${s.asOf}:${s.days}:${s.model}`,days:s.days,bias:s.bias,model:s.model,candidateId:s.id,name:s.name,protocol:research.protocol,specHash:research.specHash,engineHash:research.engineHash}));
 }
 function valid(r){return !!r&&typeof r.candidateId==='string'&&typeof r.protocol==='string'&&typeof r.specHash==='string'&&typeof r.engineHash==='string'&&(r.bias===null||['偏多','偏空','震盪'].includes(r.bias))&&root.PredictionModel.validRecord({...r,bias:r.bias||'震盪'});}
 function statistics(records,bars,calendar,events=[]){
  if(!calendar)return [];
  const groups=new Map();
  for(const r of records){
   if(!groups.has(r.model))groups.set(r.model,{model:r.model,name:r.name,days:r.days,total:0,eligible:0,signals:0,hits:0,up:0,down:0,flat:0,pending:0,excluded:0});
   const g=groups.get(r.model);g.total++;
   const o=r.outcome||root.PredictionModel.evaluate({...r,bias:r.bias||'震盪'},bars,calendar,events);
   if(o.status==='已到期'){g.eligible++;if(r.bias){g.signals++;g.hits+=o.hit?1:0;g.up+=o.realized==='偏多'?1:0;g.down+=o.realized==='偏空'?1:0;g.flat+=o.realized==='震盪'?1:0;}}
   else if(/^等待/.test(o.status))g.pending++;else g.excluded++;
  }
  return [...groups.values()].map(g=>({...g,coverage:g.eligible?100*g.signals/g.eligible:null,hitRate:g.signals?100*g.hits/g.signals:null,constantRate:g.signals?100*Math.max(g.up,g.down,g.flat)/g.signals:null}));
 }
 root.CandidateModel={capture,valid,statistics};if(typeof module!=='undefined')module.exports=root.CandidateModel;
})(typeof globalThis!=='undefined'?globalThis:this);
