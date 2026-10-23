const test=require('node:test'),assert=require('node:assert/strict');const {statistics}=require('../prediction-model.js');
const r={kind:'stock',days:5,model:'v1'};
test('命中率只用有效到期分母，等待及排除不算答錯',()=>{
 const rows=[{r,outcome:{status:'已到期',return:2,realized:'偏多',hit:true}},{r,outcome:{status:'已到期',return:-2,realized:'偏空',hit:false}},{r,outcome:{status:'等待到期 2/5',return:null}},{r,outcome:{status:'建立過晚，不納入',return:null}}];
 const g=statistics(rows)[0];assert.equal(g.hitRate,50);assert.equal(g.done,2);assert.equal(g.pending,1);assert.equal(g.excluded,1);assert.equal(g.alwaysUpRate,50);assert.equal(g.alwaysDownRate,50);assert.equal(g.constantRate,50);
});
test('天期模型類型分開，無結果不用0%冒充',()=>{
 const rows=[r,{...r,days:3},{...r,model:'v2'},{...r,kind:'sector'}].map(r=>({r,outcome:{status:'等待到期',return:null}}));
 const groups=statistics(rows);assert.equal(groups.length,4);assert(groups.every(g=>g.hitRate===null));
});
