(function(root){
const stocks=[['2330','台積電','半導體'],['2408','南亞科','記憶體'],['3037','欣興','載板'],['2409','友達','面板'],['2344','華邦電','記憶體'],['8046','南電','載板']].map(([id,name,sector])=>({id,name,sector,price:null,change:null,status:'loading'}));
function valid(h){return /^(?:[0-9]{4,6}[A-Z]?)$/.test(h.id)&&Number.isInteger(h.shares)&&h.shares>0&&h.shares<=1e8&&Number.isFinite(h.cost)&&h.cost>0&&h.cost<=1e6}
function usable(s){return s&&Number.isFinite(s.price)&&s.price>0&&['active','last_trade','previous_close'].includes(s.status)}
function summarize(holdings,quotes=stocks){let value=0,cost=0,groups={},missing=[];holdings.forEach(h=>{cost+=h.cost*h.shares;const s=quotes.find(s=>s.id===h.id);if(!usable(s)){missing.push(h.id);return}const v=s.price*h.shares;value+=v;groups[s.sector||'未分類']=(groups[s.sector||'未分類']||0)+v});const complete=!missing.length;return {value:complete?value:null,cost,pnl:complete?value-cost:null,percent:complete&&cost?(value-cost)/cost*100:null,groups,concentration:complete&&value?Math.max(...Object.values(groups))/value:null,health:null,missing}}
const api={stocks,valid,usable,summarize};root.StockModel=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
