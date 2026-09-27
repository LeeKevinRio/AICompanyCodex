import test from 'node:test';
import assert from 'node:assert/strict';
import {createGame,reviseAdjustment,restoreRecentGame,assertBalanced,totals,dealerState,analytics} from '../src/engine.js';
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
