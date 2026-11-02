const test=require('node:test'),assert=require('node:assert/strict');
global.CalendarModel=require('../calendar-model.js');
const M=require('../forecast-overview.js'),calendar={years:[2026],closed:{},opened:{},unknown:{}},now='2026-11-02T11:00:00Z';
const record=(days=3,extra={})=>({kind:'stock',id:'2330',days,asOf:'2026-11-02',bias:'偏空',model:'v5',recordedAt:'2026-11-02T10:00:00Z',...extra});
test('庫存與觀察獨立，同時存在兩邊不改變原始資料',()=>{
 const h=[{id:'2330',cost:200},{id:'8046'}],w=[{id:'2330'},{id:'2408'}],before=JSON.stringify([h,w]);
 assert.deepEqual(M.groupIds(h,w,'holdings'),['2330','8046']);assert.deepEqual(M.groupIds(h,w,'watch'),['2330','2408']);assert.equal(JSON.stringify([h,w]),before);
});
test('已封存初判優先於同日重算，3與5交易日到期獨立',()=>{
 const records=[record(),record(5)],before=JSON.stringify(records),a={id:'2330',asOf:'2026-11-02',planEnabled:true,model:'v5',forecasts:[{days:3,bias:'偏多'},{days:5,bias:'偏多'}]};
 const r=M.select('2330',a,records,calendar,now);
 assert.deepEqual(r.signals.map(s=>s.bias),['偏空','偏空']);assert.deepEqual(r.signals.map(s=>s.endDate),['2026-11-05','2026-11-09']);assert(r.signals.every(s=>s.saved&&s.active));assert.equal(JSON.stringify(records),before);
});
test('缺最新五日不能拿舊五日或歷史類比充當未來方向',()=>{
 const a={id:'2330',asOf:'2026-11-02',planEnabled:false,technicalForecasts:[{days:5,bias:'偏多'}]};
 const r=M.select('2330',a,[record(),record(5,{asOf:'2026-10-30'})],calendar,now);
 assert.equal(r.signals[1].bias,null);assert.equal(r.signals[1].active,undefined);assert.match(r.warning,/未齊/);
});
test('未封存預覽明示來源，未來日期或別股紀錄不顯示',()=>{
 const a={id:'2330',asOf:'2026-11-02',planEnabled:true,model:'v5',forecasts:[{days:3,bias:'震盪'}]};
 const r=M.select('2330',a,[record(3,{id:'2408'}),record(3,{asOf:'2026-11-03'})],calendar,now);
 assert.equal(r.signals[0].status,'分析預覽 · 未封存');assert.equal(r.signals[0].saved,false);
});
test('過期、建立過晚與未知日曆不冒充有效未來預測',()=>{
 assert.equal(M.select('2330',null,[record()],calendar,'2026-11-06T11:00:00Z').signals[0].active,false);
 assert.equal(M.select('2330',null,[record(3,{recordedAt:'2026-11-03T02:00:00Z'})],calendar,'2026-11-03T11:00:00Z').signals[0].status,'建立過晚，不納入');
 assert.equal(M.select('2330',null,[record()],null,now).signals[0].status,'交易日曆待確認');
});
