(function(root){
 function valid(s){return s&&typeof s.id==='string'&&/^[0-9]{4,6}[A-Z]?$/.test(s.id)&&typeof s.name==='string'&&s.name.length<=100&&['tse','otc'].includes(s.exchange)}
 function parse(raw){if(!raw)return [];const d=JSON.parse(raw);if(d.version!==1||!Array.isArray(d.stocks)||d.stocks.length>200||!d.stocks.every(valid)||new Set(d.stocks.map(s=>s.id)).size!==d.stocks.length)throw Error('Invalid watchlist');return d.stocks.map(({id,name,exchange})=>({id,name,exchange}));}
 function ids(holdings,watchlist){return [...new Set([...holdings.map(h=>h.id),...watchlist.map(s=>s.id)])]}
 root.TrackedStocks={parse,ids,valid};if(typeof module!=='undefined')module.exports=root.TrackedStocks;
})(typeof globalThis!=='undefined'?globalThis:this);
