const test=require('node:test'),assert=require('node:assert/strict');
const cache=require('../public-cache.js');let data;
global.localStorage={getItem:()=>data,setItem:(k,v)=>{data=v}};
test('公共資料快取保存與TTL，不把過期或未來資料當有效',()=>{cache.write('test',{quotes:[1]});assert.deepEqual(cache.read('test',1000),{quotes:[1]});data=JSON.stringify({version:1,savedAt:100,value:1});assert.equal(cache.read('test',50,200),null);assert.equal(cache.read('test',500,50),null)});
test('快取損壞、版本不符及儲存額度不足不阻斷畫面',()=>{data='{';assert.equal(cache.read('test',1000),null);data=JSON.stringify({version:2,savedAt:Date.now(),value:1});assert.equal(cache.read('test',1000),null);global.localStorage.setItem=()=>{throw Error('quota')};assert.equal(cache.write('test',{}),false)});
