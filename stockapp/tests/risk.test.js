const test=require('node:test'),assert=require('node:assert/strict');
require('../model.js');
const {tick,roundTick,plan}=require('../risk.js');
const a={planEnabled:true,bars:[{close:100}],technical:{atr:3,support:95,resistance:110,rsi:60,volumeRatio:1.5,bias:'偏多'}};
test('股票與ETF升降單位及跨級距',()=>{assert.equal(tick(9),.01);assert.equal(tick(10),.05);assert.equal(tick(100),.5);assert.equal(tick(1000),5);assert.equal(tick(49,true),.01);assert.equal(tick(50,true),.05);assert.equal(roundTick(999.9,false,true),1000);assert.equal(roundTick(49.999,true,true),50)});
test('停損、目標、持股回撤與成本損益分開',()=>{const p=plan({id:'2330',price:100,status:'active'},a,{shares:100,cost:90},10000);assert.equal(p.stop,94.2);assert.equal(p.target,110);assert.equal(p.add,110.5);assert.ok(Math.abs(p.priceRisk-580)<1e-8);assert.ok(Math.abs(p.costPnl-420)<1e-8);assert.equal(p.maxAdditionalShares,513);assert.equal(p.addReady,false)});
test('突破條件可以成立，不會讓加碼點永遠跟著現價抬高',()=>{const p=plan({id:'2330',price:111,status:'active'},a,null,1000);assert.equal(p.add,110.5);assert.equal(p.addReady,true)});
test('缺價、過期、零ATR、異常價差不產生建議',()=>{for(const s of [{id:'2330',price:100,status:'error'},{id:'2330',price:null,status:'active'},{id:'2330',price:1000,status:'active'}])assert.equal(plan(s,a,null),null);assert.equal(plan({id:'2330',price:100,status:'active'},{...a,technical:{...a.technical,atr:0}},null),null)});
test('未設定風險預算不給加碼股數，預算不足不給負股數',()=>{const s={id:'2330',price:100,status:'last_trade'};assert.equal(plan(s,a,null).maxAdditionalShares,null);assert.equal(plan(s,a,{shares:10000,cost:100},100).maxAdditionalShares,0)});


test('前一收盤僅估值，不產生交易價位',()=>assert.equal(plan({id:'2330',price:100,status:'previous_close'},a,null),null));

test('加碼同時受現金、預留費用與此股預算限制，未填不給股數',()=>{const s={id:'2330',price:100,status:'active'};assert.equal(plan(s,a,null,10000,{cash:1000,reservePercent:1}).maxAdditionalShares,8);assert.equal(plan(s,a,null,10000,{cash:0,reservePercent:1}).maxAdditionalShares,0);assert.equal(plan(s,a,null,10000,{cash:null,reservePercent:1}).maxAdditionalShares,null);assert.equal(plan(s,a,null,10000,{cash:1000,reservePercent:null}).maxAdditionalShares,null);assert.equal(plan(s,a,null,100,{cash:100000,reservePercent:1}).maxAdditionalShares,5);assert.equal(plan(s,a,{shares:10,cost:90},100,{cash:100000,reservePercent:1}).maxAdditionalShares,0)});
