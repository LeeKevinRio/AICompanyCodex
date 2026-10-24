const test=require('node:test'),assert=require('node:assert/strict');const model=require('../model.js');global.StockModel=model;const risk=require('../risk.js');
test('歷史估值獨立於行情有效性，不允許交易計畫或無資格過期資料',()=>{
 const s={id:'2330',price:100,status:'stale',valuationEligible:true};
 assert.equal(model.usable(s),false);assert.equal(model.valuationUsable(s),true);
 assert.equal(model.summarize([{id:'2330',cost:90,shares:2}],[s]).pnl,20);
 assert.equal(risk.plan(s,{planEnabled:true,technical:{atr:2,support:95,resistance:105}},null),null);
 assert.equal(model.valuationUsable({...s,valuationEligible:false}),false);
 assert.equal(model.valuationUsable({...s,status:'cached'}),false);
});
