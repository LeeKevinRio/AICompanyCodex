export const WINDS=['東','南','西','北'];
function integer(n,max=1000000){return Number.isSafeInteger(n)&&n>=0&&n<=max;}
export function validateSettings(s){
 if(!s||!Array.isArray(s.players)||s.players.length!==4||s.players.some(n=>typeof n!=='string'||!n.trim()||n.trim().length>12))throw Error('請填寫四位玩家姓名，每位最多 12 字。');
 if(new Set(s.players.map(n=>n.trim())).size!==4)throw Error('四位玩家請使用不同名稱。');
 if(!integer(s.base)||!integer(s.unit))throw Error('底與每台金額需為 0～1,000,000 的整數。');
 if(s.fee&&(!['off','fixed'].includes(s.fee.mode)||!integer(s.fee.value,1000000)||s.fee.minTai!==0||s.fee.trigger!=='self'))throw Error('請檢查東錢金額、台數與收取時機。');
 if(s.createdAt!==undefined&&!Number.isFinite(Date.parse(s.createdAt)))throw Error('牌局時間不正確。');
 if(s.initialDealer!==undefined&&!integer(s.initialDealer,3))throw Error('請選擇有效的起始莊家。');
 if(s.dealerStartHand!==undefined&&!integer(s.dealerStartHand,10000))throw Error('莊家起始位置不正確。');
 if(s.avatars&&(!Array.isArray(s.avatars)||s.avatars.length!==4||s.avatars.some(v=>!integer(v,34))))throw Error('頭像設定不正確。');
 if(typeof s.title!=='string'||!s.title.trim()||s.title.length>40)throw Error('請填寫牌局名稱，最多 40 字。');
}
export function calculate(s,h){
 validateSettings(s);
 if(!h||!['discard','self','draw'].includes(h.type))throw Error('請選擇有效的結果。');
 const delta=[0,0,0,0];if(h.type==='draw')return delta;
 if(!integer(h.winner,3)||!integer(h.tai,100))throw Error('請選擇贏家，總台數為 0～100 的整數。');
 if(h.dealer&&(!integer(h.dealer.index,3)||!integer(h.dealer.streak,10000)))throw Error('莊家狀態不正確。');
 const extra=h.dealer?1+2*h.dealer.streak:0;
 const payment=payer=>s.base+s.unit*(h.tai+(h.dealer&&(h.winner===h.dealer.index||payer===h.dealer.index)?extra:0));
 const amount=payment(h.loser);
 if(h.type==='discard'){
  if(!integer(h.loser,3)||h.loser===h.winner)throw Error('胡牌與放槍玩家不能相同。');
  delta[h.winner]=amount;delta[h.loser]=amount===0?0:-amount;
 }else{for(let i=0;i<4;i++)if(i!==h.winner){const due=payment(i);delta[i]=due===0?0:-due;delta[h.winner]+=due;}}
 return delta;
}
export function handResult(game,h){
 const s=h.rules?{...game,...h.rules}:game;const delta=calculate(s,h);let fee=0;
 if(h.type==='self'&&s.fee&&s.fee.mode==='fixed'){
  const gross=delta[h.winner];fee=s.fee.value;fee=Math.min(gross,fee);delta[h.winner]-=fee;
 }return {delta,fee};
}
export function adjustmentDelta(a){if(!a||!Array.isArray(a.delta)||a.delta.length!==4||a.delta.some(v=>!Number.isSafeInteger(v)||Math.abs(v)>3000000)||a.delta.reduce((x,y)=>x+y,0)!==0||a.delta.every(v=>v===0)||typeof a.note!=='string'||!a.note.trim()||a.note.length>80)throw Error('調整需填原因、四家金額為整數且加總為0，單人最多300萬元。');return a.delta;}
export function totals(game){const base=game.hands.reduce((a,h)=>handResult(game,h).delta.map((x,i)=>x+a[i]),[0,0,0,0]);return (game.adjustments??[]).reduce((sum,a)=>adjustmentDelta(a).map((v,i)=>v+sum[i]),base);}
export function reviseHand(game,index,replacement){if(!Number.isInteger(index)||index<0||index>=game.hands.length)throw Error('找不到紀錄');const next=structuredClone(game);next.hands[index]={...replacement,createdAt:game.hands[index].createdAt,rules:game.hands[index].rules??rulesSnapshot(game)};for(let i=index;i<next.hands.length;i++){const h=next.hands[i];if(next.initialDealer!==undefined&&i>=(next.dealerStartHand??0))h.dealer=dealerState({...next,hands:next.hands.slice(0,i)});else delete h.dealer;handResult(next,h);}next.revisions??=[];next.revisions.push({index,before:structuredClone(game.hands[index]),after:structuredClone(next.hands[index]),at:new Date().toISOString()});return next;}
export function houseTotal(game){return game.hands.reduce((sum,h)=>sum+handResult(game,h).fee,0);}
export function rulesSnapshot(game){return {base:game.base,unit:game.unit,fee:structuredClone(game.fee??{mode:'off',value:0,minTai:0,trigger:'self'})};}
export function settlement(game){
 const b=[...totals(game),houseTotal(game)];const debt=b.map((v,i)=>({i,n:-v})).filter(x=>x.n>0),credit=b.map((v,i)=>({i,n:v})).filter(x=>x.n>0),out=[];
 for(const d of debt)for(const c of credit){const amount=Math.min(d.n,c.n);if(amount){out.push({from:d.i,to:c.i,amount});d.n-=amount;c.n-=amount;}}return out;
}
export function createGame(settings){validateSettings(settings);return {...structuredClone(settings),players:settings.players.map(x=>x.trim()),title:settings.title.trim(),id:crypto.randomUUID(),createdAt:settings.createdAt??new Date().toISOString(),endedAt:null,hands:[]};}
export function validateStore(data){
 if(!data||data.version!==1||!Array.isArray(data.games)||data.games.length>500)throw Error('牌局資料格式不正確。');
 if(data.players!==undefined){if(!Array.isArray(data.players)||data.players.some(p=>!p||typeof p.id!=='string'||typeof p.name!=='string'||!p.name.trim()||p.name.length>12||!integer(p.avatar,34))||new Set(data.players.map(p=>p.id)).size!==data.players.length)throw Error('玩家列表格式錯誤。');}
 const ids=new Set();
 for(const g of data.games){validateSettings(g);if(g.adjustments!==undefined){if(!Array.isArray(g.adjustments)||g.adjustments.length>10000)throw Error("調整紀錄格式錯誤");g.adjustments.forEach(adjustmentDelta);}if(g.playerIds&&(!Array.isArray(g.playerIds)||g.playerIds.length!==4||new Set(g.playerIds).size!==4||g.playerIds.some(id=>!data.players?.some(p=>p.id===id))))throw Error('牌局玩家身分不完整。');if(typeof g.id!=='string'||ids.has(g.id)||!Array.isArray(g.hands)||g.hands.length>10000||!Number.isFinite(Date.parse(g.createdAt))||(g.endedAt!==null&&!Number.isFinite(Date.parse(g.endedAt))))throw Error('牌局資料不完整。');ids.add(g.id);for(const h of g.hands){handResult(g,h);if(typeof h.note!=='string'||h.note.length>80)throw Error('紀錄備註格式錯誤。');}}
 if(data.activeId!==null&&!data.games.some(g=>g.id===data.activeId&&!g.endedAt))throw Error('目前牌局不存在。');return data;
}

export function analytics(game){
 const resolved=game.hands.filter(h=>h.type!=='draw').length;
 const rows=game.players.map((name,i)=>({name,index:i,wins:0,self:0,discard:0,dealIn:0,tai:0,fee:0,net:0,winRate:null,selfRate:null,nextRate:null,maxTai:null,maxWin:0,maxLoss:0,idle:0,active:0,grossWin:0,selfIncome:0,sumSq:0}));
 const trend=[[0,0,0,0]];
 for(const h of game.hands){const r=handResult(game,h);trend.push(r.delta.map((v,i)=>v+trend.at(-1)[i]));r.delta.forEach((v,i)=>{const row=rows[i];if(v===0)row.idle++;else row.active++;row.maxWin=Math.max(row.maxWin,v);row.maxLoss=Math.max(row.maxLoss,-v);row.sumSq+=v*v;if(v>0){row.grossWin+=v;if(h.type==='self')row.selfIncome+=v;}});if(h.type==='draw')continue;
 const w=rows[h.winner];w.wins++;w.tai+=h.tai;w.maxTai=Math.max(w.maxTai??0,h.tai);w.fee+=r.fee;if(h.type==='self')w.self++;else {w.discard++;rows[h.loser].dealIn++;}}
 rows.forEach((r,i)=>{r.playNet=trend.at(-1)[i];r.net=totals(game)[i];r.idleRate=game.hands.length?r.idle/game.hands.length:null;r.volatility=game.hands.length?Math.sqrt(Math.max(0,r.sumSq/game.hands.length-(trend.at(-1)[i]/game.hands.length)**2)):null;r.selfShare=r.wins?r.self/r.wins:null;r.winRate=resolved?r.wins/resolved:null;r.selfRate=resolved?r.self/resolved:null;r.nextRate=resolved?rows[(i+1)%4].wins/resolved:null;r.dealInRate=resolved?r.dealIn/resolved:null;r.averageTai=r.wins?r.tai/r.wins:null;});
 return {resolved,draws:game.hands.length-resolved,rows,trend};
}

export function dealerState(game){
 if(game.initialDealer===undefined)return null;
 let index=game.initialDealer,streak=0,rotations=0;
 for(const h of game.hands.slice(game.dealerStartHand??0)){if(h.type==='draw'||h.winner===index)streak++;else {index=(index+1)%4;streak=0;rotations++;}}
 return {index,streak,rotations};
}

export function migratePlayers(data){
 const next=structuredClone(data);next.players??=[];
 for(const g of next.games){if(g.playerIds)continue;g.playerIds=g.players.map((name,i)=>{let p=next.players.find(p=>p.name===name);if(!p){p={id:crypto.randomUUID(),name,avatar:g.avatars?.[i]??i};next.players.push(p);}return p.id;});}return next;
}
export function playerTotals(data,id,period=''){
 const result={games:0,hands:0,resolved:0,wins:0,self:0,dealIn:0,tai:0,fee:0,net:0,playNet:0,maxTai:null,maxWin:0,maxLoss:0,idle:0,active:0,sumSq:0,history:[]};
 for(const g of data.games){if(period&&!taipeiDate(g.createdAt).startsWith(period))continue;const i=g.playerIds?.indexOf(id)??-1;if(i<0)continue;const a=analytics(g),r=a.rows[i];result.games++;result.hands+=g.hands.length;result.resolved+=a.resolved;for(const k of ['wins','self','dealIn','tai','fee','net','playNet'])result[k]+=r[k];result.maxTai=r.maxTai===null?result.maxTai:Math.max(result.maxTai??0,r.maxTai);result.maxWin=Math.max(result.maxWin,r.maxWin);result.maxLoss=Math.max(result.maxLoss,r.maxLoss);result.idle+=r.idle;result.active+=r.active;result.sumSq+=r.sumSq;result.history.push({id:g.id,title:g.title,createdAt:g.createdAt,net:r.net,hands:g.hands.length});}
 return {...result,idleRate:result.hands?result.idle/result.hands:null,selfShare:result.wins?result.self/result.wins:null,volatility:result.hands?Math.sqrt(Math.max(0,result.sumSq/result.hands-(result.playNet/result.hands)**2)):null,winRate:result.resolved?result.wins/result.resolved:null,selfRate:result.resolved?result.self/result.resolved:null,dealInRate:result.resolved?result.dealIn/result.resolved:null};
}
export function gameProgress(g){const d=dealerState(g);if(!d)return {label:'舊牌局：將數未追蹤',completed:null};const completed=Math.floor(d.rotations/16);return {completed,label:`${completed} 將完成 · 第 ${completed+1} 將 ${WINDS[Math.floor(d.rotations/4)%4]}風 ${d.rotations%4+1} 局`};}

export function taipeiDate(value){const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(value));const get=k=>parts.find(p=>p.type===k).value;return `${get('year')}-${get('month')}-${get('day')}`;}
