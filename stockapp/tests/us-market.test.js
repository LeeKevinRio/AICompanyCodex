const test=require('node:test'),assert=require('node:assert/strict'),M=require('../us-market.js');
test('美股小數股與美元損益，未知行情不算0且不混台幣',()=>{
 const raw=JSON.stringify({version:1,holdings:[{symbol:'AAPL',exchange:'NMS',shares:1.5,cost:100}],watch:['NVDA']});
 const state=M.parse(raw),now=Date.parse('2026-11-01T10:00:00Z'),q=new Map([['AAPL',{currency:'USD',price:110,quotedAt:'2026-10-30T20:00:00Z'}]]);
 assert.equal(M.totals(state.holdings,q,now).pnl,15);
 q.get('AAPL').currency='TWD';assert.equal(M.totals(state.holdings,q,now).pnl,null);
 assert.equal(M.totals(state.holdings,new Map(),now).value,null);
 assert.equal(raw,JSON.stringify({version:1,holdings:[{symbol:'AAPL',exchange:'NMS',shares:1.5,cost:100}],watch:['NVDA']}));
});
test('美股損壞或重複資料拒絕讀取，不吞掉私人資料',()=>{
 assert.throws(()=>M.parse('{broken'));
 for(const cost of [0,-1,Infinity])assert.throws(()=>M.parse(JSON.stringify({version:1,holdings:[{symbol:'AAPL',exchange:'NMS',shares:1,cost}],watch:[]})));
 assert.throws(()=>M.parse(JSON.stringify({version:1,holdings:[],watch:['AAPL','AAPL']})));
 assert.deepEqual(M.parse(null),{version:1,holdings:[],watch:[]});
});
test('美股報價過期或未來時間不計算估值',()=>{
 const h=[{symbol:'AAPL',shares:1,cost:100}],now=Date.parse('2026-11-01T10:00:00Z');
 for(const quotedAt of ['bad','2026-10-01T00:00:00Z','2026-11-02T00:00:00Z'])assert.equal(M.totals(h,new Map([['AAPL',{currency:'USD',price:110,quotedAt}]]),now).pnl,null);
});

test('曲線期間只截取真實資料，不補點且不修改來源',()=>{const bars=Array.from({length:40},(_,i)=>({date:String(i),close:i+1}));const selected=M.series(bars,21);assert.equal(selected.length,21);assert.equal(selected[0].close,20);selected[0].close=999;assert.equal(bars[19].close,20);assert.equal(M.series(bars,126).length,40)});
