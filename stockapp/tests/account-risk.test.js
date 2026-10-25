const test=require('node:test'),assert=require('node:assert/strict');const {simulate}=require('../account-risk.js');
const row={id:'2330',heldShares:10,addShares:10,entry:100,current:95,stop:90,valid:true,maxAdditional:100};
test('共同現金僅一份，多股合計超額不能各自通過',()=>{
 const r=simulate([row,{...row,id:'8046'}],1500,1000,0);
 assert.equal(r.cashNeeded,2000);assert.equal(r.risk,300);assert.equal(r.valid,false);assert(r.issues.some(t=>t.includes('共同現金')));
});
test('風險包含既有部位及費用，缺資料不報安全',()=>{
 assert.equal(simulate([row],2000,200,1).risk,169.5);
 assert.equal(simulate([row],2000,160,1).valid,false);
 assert.equal(simulate([{...row,valid:false}],2000,1000,0).known,0);
 assert.equal(simulate([row],null,1000,0).valid,false);
 assert.equal(simulate([{...row,maxAdditional:null}],2000,1000,0).valid,false);
 assert.equal(simulate([{...row,addShares:-1}],2000,1000,0).valid,false);
 assert.equal(simulate([row,row],3000,1000,0).valid,false);
});
