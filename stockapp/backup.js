(function(root){
 function parse(text){const data=JSON.parse(text);if(!data||data.version!==2||!Array.isArray(data.holdings)||data.holdings.length>2000)throw Error('備份格式不支援，請使用晴盤版本2 JSON。');const rows=data.holdings.map(h=>({id:h.id,shares:h.shares,cost:h.cost}));if(!rows.every(h=>typeof h.id==='string'&&root.StockModel.valid(h))||new Set(rows.map(h=>h.id)).size!==rows.length)throw Error('備份有無效或重複庫存，未匯入。');return rows}
 function merge(current,incoming){const ids=new Set(current.map(h=>h.id));return [...current,...incoming.filter(h=>!ids.has(h.id))]}
 root.StockBackup={parse,merge};if(typeof module!=='undefined')module.exports=root.StockBackup;
})(typeof globalThis!=='undefined'?globalThis:this);
