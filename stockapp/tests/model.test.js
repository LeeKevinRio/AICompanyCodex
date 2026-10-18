const test=require('node:test'),assert=require('node:assert/strict');
const {stocks,summarize,valid,usable}=require('../model.js');
test('空庫存不產生虛假健康度與持股',()=>{const a=summarize([]);assert.equal(a.health,null);assert.equal(a.value,0);assert.equal(a.concentration,null);assert.equal(a.percent,null);assert.ok(stocks.every(s=>s.price===null))});
test('有效行情時計算損益與集中度',()=>{const a=summarize([{id:'2330',shares:1000,cost:980},{id:'2408',shares:2000,cost:64}],[{id:'2330',price:1040,status:'active',sector:'半導體'},{id:'2408',price:68.5,status:'last_trade',sector:'記憶體'}]);assert.equal(a.value,1177000);assert.equal(a.cost,1108000);assert.equal(a.pnl,69000);assert.equal(a.concentration,1040000/1177000)});
test('拒絕未知股票、小數股數、負成本與無限值',()=>{for(const h of [{id:'xxx',shares:1,cost:1},{id:'2330',shares:1.2,cost:1},{id:'2330',shares:1,cost:-1},{id:'2330',shares:1,cost:Infinity}])assert.equal(valid(h),false);assert.equal(valid({id:'2330',shares:1000,cost:980}),true)});
test('缺價過期與連線失敗不得算作零損益',()=>{for(const status of ['error','stale','missing','loading','no_trade']){const a=summarize([{id:'2330',shares:1000,cost:1000}],[{id:'2330',price:1200,status}]);assert.equal(a.value,null);assert.equal(a.pnl,null);assert.deepEqual(a.missing,['2330'])}});
test('可輸入非預設股票與ETF代碼',()=>{assert.ok(valid({id:'6488',shares:1000,cost:100}));assert.ok(valid({id:'0050',shares:100,cost:100}));assert.ok(valid({id:'00981A',shares:1000,cost:10}));assert.equal(usable({price:null,status:'active'}),false)});

test('前一收盤參考估值可計算持股市值',()=>assert.equal(summarize([{id:'2330',shares:10,cost:90}],[{id:'2330',price:100,status:'previous_close'}]).value,1000));
