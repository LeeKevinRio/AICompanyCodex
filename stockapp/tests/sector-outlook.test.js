const test=require('node:test'),assert=require('node:assert/strict');
const {summarize}=require('../sector-outlook.js');
const now=Date.parse('2026-10-14T20:00:00+08:00');
const a=(bias,date='2026-10-13')=>({loadedAt:now,asOf:date,planEnabled:true,forecasts:[{days:5,bias}]});
test('五日情境獨立於當日漲跌，60%方向票決',()=>{const r=summarize([a('偏空'),a('偏空'),a('偏空'),a('偏多'),a('震盪')],100,5,now);assert.equal(r.bias,'偏空');assert.equal(r.total,100)});
test('不足涵蓋、過期或停用分析不產生天氣',()=>{assert.equal(summarize([a('偏多')],100,12,now).ready,false);assert.equal(summarize([{...a('偏多'),planEnabled:false}],1,1,now).ready,false);assert.equal(summarize([{...a('偏多'),loadedAt:now-1800001}],1,1,now).ready,false)});
test('不同日線日期不混算且小族群需全部有效',()=>{assert.equal(summarize([a('偏多'),a('偏空','2026-10-12')],2,2,now).ready,false);assert.equal(summarize([a('偏多'),a('偏多')],2,2,now).bias,'偏多')});
test('方向分歧為震盪，僅3日情境不能充當5日',()=>{assert.equal(summarize([a('偏多'),a('偏多'),a('偏空'),a('偏空'),a('震盪')],5,5,now).bias,'震盪');assert.equal(summarize([{...a('偏多'),forecasts:[{days:3,bias:'偏多'}]}],1,1,now).ready,false)});

test('收盤優先最新日期，不選舊日較多檔數；全數下跌不得算成上漲',()=>{const {latestClose}=require('../sector-outlook.js');const r=latestClose([{date:'2026-10-14',change:2},{date:'2026-10-14',change:5},{date:'2026-10-15',change:-6}]);assert.equal(r.date,'2026-10-15');assert.equal(r.change,-6);assert.equal(r.rows.length,1);assert.equal(latestClose([{date:'2026-10-15',change:-6},{date:'2026-10-15',change:-8}]).change,-7);assert.equal(latestClose([]).change,null)});

test('族群規則日線不得落後已收盤行情日期',()=>{const r=summarize([a('偏多')],1,1,now,'2026-10-14');assert.equal(r.ready,false);assert.equal(r.reason,'日線日期待同步')});
