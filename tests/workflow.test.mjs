import test from 'node:test';
import assert from 'node:assert/strict';
import {rematchSettings,singleGameBackup,migratePlayers,playerTotals,validateStore,moneyTrend,ledgerEvents,createGame,reviseAdjustment,restoreRecentGame,assertBalanced,totals,dealerState,analytics} from '../src/engine.js';
const game=()=>createGame({title:'流程測試',players:['甲','乙','丙','丁'],base:100,unit:20,initialDealer:0});
test('修正收付保留原時間與修改歷程，不改莊家及打牌統計',()=>{
 const g=game();g.adjustments=[{delta:[-300,100,100,100],note:'詐胡',createdAt:'2026-09-27T01:00:00Z'}];
 const next=reviseAdjustment(g,0,{delta:[-200,200,0,0],note:'更正'});
 assert.deepEqual(totals(next),[-200,200,0,0]);assert.equal(next.adjustments[0].createdAt,g.adjustments[0].createdAt);
 assert.deepEqual(next.adjustmentRevisions[0].before,g.adjustments[0]);assert.deepEqual(dealerState(next),dealerState(g));
 assert.equal(analytics(next).resolved,0);assert.deepEqual(totals(g),[-300,100,100,100]);assertBalanced(next);
 assert.throws(()=>reviseAdjustment({...g,endedAt:new Date().toISOString()},0,next.adjustments[0]));
});
test('立即撤銷僅允許還原未再變動的同一牌局',()=>{
 const before=game(),after=structuredClone(before);after.hands.push({type:'draw',note:''});
 assert.deepEqual(restoreRecentGame(after,before,after),before);
 const changed=structuredClone(after);changed.hands.push({type:'draw',note:''});
 assert.throws(()=>restoreRecentGame(changed,before,after));
 assert.throws(()=>restoreRecentGame({...after,endedAt:new Date().toISOString()},before,after));
});

test('全部曲線依時間整合收付，終值對齊結算；打牌曲線排除收付',()=>{
 const g=game();g.hands=[{type:'discard',winner:0,loser:1,tai:1,note:'',createdAt:'2026-09-27T02:00:00Z'}];
 g.adjustments=[{delta:[-300,100,100,100],note:'詐胡',createdAt:'2026-09-27T01:00:00Z'}];
 assert.equal(ledgerEvents(g)[0].kind,'adjustment');
 assert.deepEqual(moneyTrend(g,'all').at(-1),totals(g));
 assert.deepEqual(moneyTrend(g,'play').at(-1),[120,-120,0,0]);
 assert.deepEqual(moneyTrend(game(),'all'),[[0,0,0,0]]);
});

test('練習局重新載入與匯入不新增人物，不計玩家累計',()=>{
 const g=game();g.practice=true;g.playerIds=['a','b','c','d'];g.hands=[{type:'self',winner:0,tai:1,note:''}];
 const players=g.players.map((name,i)=>({id:g.playerIds[i],name,avatar:i}));
 const store={version:1,players,games:[g],activeId:g.id};
 assert.equal(playerTotals(store,'a').games,0);assert.equal(playerTotals(store,'a').net,0);
 delete g.playerIds;const restored=migratePlayers(validateStore(JSON.parse(JSON.stringify({...store,players:[]}))));
 assert.equal(restored.players.length,0);assert.equal(restored.games[0].practice,true);
});
test('沿用只複製設定與人物，不複製牌局身份帳務',()=>{
 const g=game();g.playerIds=['a','b','c','d'];g.hands=[{type:'draw',note:''}];g.adjustments=[{delta:[-300,100,100,100],note:'詐胡'}];
 const next=createGame(rematchSettings(g,'2026-09-27T03:00:00Z'));
 assert.notEqual(next.id,g.id);assert.equal(next.createdAt,'2026-09-27T03:00:00Z');assert.deepEqual(next.hands,[]);assert.equal(next.adjustments,undefined);assert.deepEqual(next.playerIds,g.playerIds);assert.deepEqual(totals(next),[0,0,0,0]);
});
test('單桌備份只包含相關人物與一桌，可驗證並匯入',()=>{
 const g=game();g.playerIds=['a','b','c','d'];const players=g.players.map((name,i)=>({id:g.playerIds[i],name,avatar:i}));
 const s={version:1,players:[...players,{id:'other',name:'其他人',avatar:0}],games:[g,game()],activeId:g.id};
 const backup=singleGameBackup(s,g.id);assert.equal(backup.players.length,4);assert.equal(backup.games.length,1);assert.equal(validateStore(backup).activeId,g.id);backup.games[0].title='修改';assert.notEqual(s.games[0].title,'修改');
});
