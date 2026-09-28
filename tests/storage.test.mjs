import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {validateStore,assertBalanced} from '../src/engine.js';
const source=readFileSync(new URL('../src/app.js',import.meta.url),'utf8');
const saveSource=source.slice(source.indexOf('function save(next)'),source.indexOf('function mutate('));
function context(){
 const store={version:1,players:[],games:[],activeId:null},raw=JSON.stringify(store);
 const form={dataset:{},value:'保留輸入',querySelector:()=>null,append(node){this.warning=node;}};
 const c={store,diskSnapshot:raw,KEY:'test',loadBlocked:false,storageError:'',backupMeta:{},crypto,validateStore,assertBalanced,toast:()=>{},saveBackupMeta:()=>{},$:()=>form,document:{querySelectorAll:()=>[form],createElement:()=>({setAttribute(){}})},localStorage:{getItem:()=>raw,setItem(){throw Error('QuotaExceededError');}}};
 vm.createContext(c);vm.runInContext(saveSource,c);return {c,form};
}
test('空間不足不改記憶或磁碟基線，保留輸入且可重試',()=>{
 const {c,form}=context(),before=JSON.stringify(c.store),next={...c.store,players:[{id:'1',name:'甲',avatar:0}]};
 assert.equal(c.save(next),false);assert.equal(JSON.stringify(c.store),before);assert.equal(c.diskSnapshot,before);assert.equal(form.value,'保留輸入');assert.match(form.warning.textContent,/儲存失敗/);assert.equal(form.dataset.saved,undefined);
 c.localStorage.setItem=()=>{};assert.equal(c.save(next),true);assert.equal(c.store.players.length,1);assert.equal(form.dataset.saved,'true');
});
test('另一分頁已變動時拒絕覆蓋',()=>{
 const {c}=context();let written=false;c.localStorage.getItem=()=>'{"different":true}';c.localStorage.setItem=()=>{written=true;};
 assert.equal(c.save(c.store),false);assert.equal(written,false);assert.match(c.storageError,/其他分頁/);
});
