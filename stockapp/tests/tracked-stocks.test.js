const test=require('node:test'),assert=require('node:assert/strict');const {parse,ids}=require('../tracked-stocks.js');
test('追蹤範圍隨持股及自選增減，重複股票只出現一次',()=>{
 const h=[{id:'2330'},{id:'8046'}],watch=[{id:'2330'},{id:'2408'}];
 assert.deepEqual(ids(h,watch),['2330','8046','2408']);assert.deepEqual(ids(h.slice(1),watch.slice(1)),['8046','2408']);
 assert.deepEqual(h,[{id:'2330'},{id:'8046'}]);
});
test('觀察清單僅保存身份，損壞或重複資料不讀取覆寫',()=>{
 const s={id:'2330',name:'台積電',exchange:'tse',cost:999};
 assert.deepEqual(parse(JSON.stringify({version:1,stocks:[s]})),[{id:'2330',name:'台積電',exchange:'tse'}]);
 assert.throws(()=>parse('{'));assert.throws(()=>parse(JSON.stringify({version:1,stocks:[s,s]})));
 assert.deepEqual(parse(null),[]);
});
