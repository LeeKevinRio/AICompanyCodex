const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const CalendarModel=require('../calendar-model.js');
function context(raw=null){const c=vm.createContext({CalendarModel,Date,localStorage:{getItem:()=>raw},document:{addEventListener(){}}});vm.runInContext(fs.readFileSync(require.resolve('../daily-run.js'),'utf8'),c);return c}
test('每日執行以台北日期及官方日曆辨識休市、交易日與涵蓋不足',()=>{const c=context();c.cal={years:[2026],closed:{'2026-10-26':'補假'},opened:{},unknown:{}};assert.equal(vm.runInContext("dailyDayState('2026-10-25T10:00:00Z',cal).state",c),'closed');assert.equal(vm.runInContext("dailyDayState('2026-10-26T10:00:00Z',cal).state",c),'closed');assert.equal(vm.runInContext("dailyDayState('2026-10-27T10:00:00Z',cal).state",c),'open');assert.equal(vm.runInContext("dailyDayState('2027-02-01T10:00:00Z',cal).state",c),'unknown')});
test('損壞每日執行紀錄禁止覆寫',()=>{const c=context('{broken');assert(vm.runInContext('dailyError.length>0',c));assert.equal(vm.runInContext('dailyRuns.length',c),0)});
test('交易日可保存成功證據，重跑不重複預測，資料落後則跳過',async()=>{
 class FixedDate extends Date{constructor(...args){super(...(args.length?args:['2026-10-27T09:30:00Z']))}}
 const refreshCalls=[],storage=new Map(),records=[],a={id:'2330',asOf:'2026-10-27',pipelineVersion:'calendar-actions-v4',planEnabled:true};
 const c=vm.createContext({CalendarModel,Date:FixedDate,localStorage:{getItem:()=>null,setItem:(k,v)=>storage.set(k,v)},document:{addEventListener(){}},render(){},loadMarketContext:async force=>refreshCalls.push(force),marketContext:{calendar:{years:[2026],closed:{},opened:{},unknown:{}}},trackedIds:()=>['2330'],stocks:[{id:'2330'}],loadAnalysis:async()=>{},analysisCache:new Map([['2330',a]]),analysisErrors:new Map(),predictionRecords:records,journalError:'',rememberPrediction:()=>{for(const days of [3,5])if(!records.some(r=>r.days===days))records.push({key:String(days),kind:'stock',id:'2330',asOf:a.asOf,days,model:a.model})},checkPredictions:async()=>{}});
 vm.runInContext(fs.readFileSync(require.resolve('../daily-run.js'),'utf8'),c);
 await vm.runInContext('runDailyPredictions()',c);assert.equal(vm.runInContext('dailyRuns[0].status',c),'完成');assert.equal(records.length,2);assert.equal(refreshCalls[0],true);
 await vm.runInContext('runDailyPredictions()',c);assert.equal(records.length,2);assert.equal(vm.runInContext('dailyRuns[1].rows[0].status',c),'已存在，未重複');
 a.asOf='2026-10-22';await vm.runInContext('runDailyPredictions()',c);assert.equal(vm.runInContext('dailyRuns[2].status',c),'資料未齊');assert.equal(records.length,2);assert(storage.size>0);
});
