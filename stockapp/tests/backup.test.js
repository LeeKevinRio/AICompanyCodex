const test=require('node:test'),assert=require('node:assert/strict');
global.StockModel=require('../model.js');const {parse,merge}=require('../backup.js');
const h={id:'2330',shares:100,cost:100};
test('備份解析移除非庫存欄位並保留有效數字',()=>assert.deepEqual(parse(JSON.stringify({version:2,holdings:[{...h,secret:'unused'}]})),[h]));
test('重複或無效輸入拒絕整批匯入',()=>{for(const rows of [[h,h],[{...h,cost:-1}],[{...h,shares:1.5}]])assert.throws(()=>parse(JSON.stringify({version:2,holdings:rows})));assert.throws(()=>parse('{'));assert.throws(()=>parse('null'));assert.throws(()=>parse(JSON.stringify({version:2,holdings:[{...h,id:2330}]})));assert.throws(()=>parse(JSON.stringify({version:1,holdings:[h]})))});
test('合併保護現有股數成本，新增缺少股票且不改輸入',()=>{const current=[h],incoming=[{...h,cost:200},{id:'6488',shares:5,cost:300}];assert.deepEqual(merge(current,incoming),[h,incoming[1]]);assert.equal(current.length,1);assert.equal(incoming[0].cost,200)});
