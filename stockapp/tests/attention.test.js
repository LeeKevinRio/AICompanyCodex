const {test}=require('node:test');const assert=require('node:assert/strict');const {build}=require('../attention.js');
test('注意清單排除空庫存，不把週末前收當壞行情，成本集中可辨識',()=>{
 assert.deepEqual(build([],[],new Map()),[]);
 const h=[{id:'2330',cost:100,shares:1}],s=[{id:'2330',name:'台積電',price:101,status:'previous_close',quotedAt:'2026-10-16T13:30:00'}];
 const a=new Map([['2330',{pipelineVersion:'calendar-actions-v2',loadedAt:1000,asOf:'2026-10-16',planEnabled:true}]]);
 const r=build(h,s,a,1001);assert.equal(r.length,1);assert.match(r[0].reason,/投入成本/);
});
test('缺價及跨事件先顯示；過期分析不冒充有效分析',()=>{
 const h=[{id:'2330',cost:100,shares:1}];const a=new Map([['2330',{pipelineVersion:'calendar-actions-v2',loadedAt:0,planEnabled:true,nextSessions:['2026-10-19'],corporateActions:[{date:'2026-10-19',kind:'除息'},{date:'2027-01-01',kind:'除息'}]}]]);
 const r=build(h,[],a,1800001);assert.equal(r[0].priority,0);assert(r.some(x=>/過期/.test(x.reason)));assert.equal(r.filter(x=>/跨事件/.test(x.reason)).length,1);
});
