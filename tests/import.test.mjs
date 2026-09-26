import test from 'node:test';
import assert from 'node:assert/strict';
import {createGame,migratePlayers,importPlan,mergeImport} from '../src/engine.js';
const fixture=()=>{const g=createGame({title:'測試',players:['甲','乙','丙','丁'],base:100,unit:20,fee:{mode:'off',value:0,minTai:0,trigger:'self'}});return migratePlayers({version:1,games:[g],activeId:g.id});};
test('匯入相同資料無衝突，JSON欄位順序不影響比較',()=>{const a=fixture(),b=JSON.parse(JSON.stringify(a));b.games[0]=Object.fromEntries(Object.entries(b.games[0]).reverse());assert.ok(importPlan(a,b).every(e=>e.status==='same'));assert.deepEqual(mergeImport(a,b),a);});
test('衝突需逐筆決策，保留本機或採匯入且原物件不變',()=>{const a=fixture(),b=structuredClone(a);b.games[0].base=200;b.players[0].avatar=9;assert.throws(()=>mergeImport(a,b));const choices=Object.fromEntries(importPlan(a,b).filter(e=>e.status==='conflict').map(e=>[e.kind+':'+e.id,'incoming']));const n=mergeImport(a,b,choices);assert.equal(n.games[0].base,200);assert.equal(n.players[0].avatar,9);assert.equal(a.games[0].base,100);for(const k in choices)choices[k]='local';assert.deepEqual(mergeImport(a,b,choices),a);});
test('合併新牌局保留現有牌局與身分，重複匯入不重複',()=>{const a=fixture(),b=fixture(),n=mergeImport(a,b);assert.equal(n.games.length,2);assert.equal(n.activeId,a.activeId);assert.equal(mergeImport(n,b).games.length,2);});
test('替換進行中牌局為已結束版本時修復activeId',()=>{const a=fixture(),b=structuredClone(a);b.games[0].endedAt=new Date().toISOString();b.activeId=null;const n=mergeImport(a,b,{['games:'+a.games[0].id]:'incoming'});assert.equal(n.activeId,null);});
test('損壞匯入不改動目前資料',()=>{const a=fixture(),before=JSON.stringify(a);assert.throws(()=>mergeImport(a,{version:99,games:[]}));assert.equal(JSON.stringify(a),before);});
