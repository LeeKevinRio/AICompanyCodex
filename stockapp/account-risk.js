(function(root){
 function simulate(rows,cash,budget,reserve){
  const issues=[];let cashNeeded=0,risk=0,known=0;
  if(!Number.isFinite(cash)||cash<0)issues.push('尚未設定可用現金');
  if(!Number.isFinite(reserve)||reserve<0||reserve>100)issues.push('尚未設定費用與滑價緩衝');
  if(!Number.isFinite(budget)||budget<=0)issues.push('尚未設定帳戶總風險預算');
  const seen=new Set();
  for(const row of rows){
   if(seen.has(row.id)){issues.push('重複部位');continue}seen.add(row.id);
   if(!Number.isInteger(row.addShares)||row.addShares<0){issues.push(row.id+' 加碼股數無效');continue}
   if(!Number.isInteger(row.heldShares)||row.heldShares<0){issues.push(row.id+' 庫存股數無效');continue}
   if(!row.valid||!Number.isFinite(row.entry)||!Number.isFinite(row.current)||!Number.isFinite(row.stop)||row.stop<=0||row.entry<=row.stop||row.current<=row.stop){issues.push(row.id+' 缺有效行情／風險價位');continue}
   known++;const buffer=Number.isFinite(reserve)?reserve/100:0;
   if(row.addShares>0&&(!Number.isFinite(row.maxAdditional)||row.addShares>row.maxAdditional))issues.push(row.id+' 超過單股可加碼上限或尚未設定預算');
   cashNeeded+=row.addShares*row.entry*(1+buffer);
   risk+=row.heldShares*(row.current-row.stop+row.current*buffer)+row.addShares*(row.entry-row.stop+row.entry*buffer);
  }
  if(Number.isFinite(cash)&&cashNeeded>cash)issues.push('合計加碼金額超過共同現金');
  if(Number.isFinite(budget)&&risk>budget)issues.push('合計觀察風險超過帳戶預算');
  return {cashNeeded,risk,cashRemaining:Number.isFinite(cash)?cash-cashNeeded:null,known,total:rows.length,valid:issues.length===0&&rows.length>0,issues};
 }
 root.AccountRisk={simulate};if(typeof module!=='undefined')module.exports=root.AccountRisk;
})(typeof globalThis!=='undefined'?globalThis:this);
