(function(root){
 function read(key,maxAge,now=Date.now()){try{const d=JSON.parse(localStorage.getItem(key));return d?.version===1&&Number.isFinite(d.savedAt)&&d.savedAt<=now&&now-d.savedAt<maxAge?d.value:null}catch{return null}}
 function write(key,value){try{localStorage.setItem(key,JSON.stringify({version:1,savedAt:Date.now(),value}));return true}catch{return false}}
 let database=null;
 function openLarge(){if(database)return database;database=new Promise(resolve=>{if(!root.indexedDB){resolve(null);return}const r=root.indexedDB.open('clearsignal-public-analysis-v1',1);r.onupgradeneeded=()=>{if(!r.result.objectStoreNames.contains('values'))r.result.createObjectStore('values')};r.onsuccess=()=>resolve(r.result);r.onerror=()=>resolve(null);r.onblocked=()=>resolve(null)});return database}
 async function readLarge(key){try{const db=await openLarge();if(!db)return null;return await new Promise(resolve=>{const r=db.transaction('values','readonly').objectStore('values').get(key);r.onsuccess=()=>resolve(r.result||null);r.onerror=()=>resolve(null)})}catch{return null}}
 async function writeLarge(key,value){try{const db=await openLarge();if(!db)return false;return await new Promise(resolve=>{const t=db.transaction('values','readwrite');t.objectStore('values').put(value,key);t.oncomplete=()=>resolve(true);t.onerror=()=>resolve(false);t.onabort=()=>resolve(false)})}catch{return false}}
 root.PublicCache={read,write,readLarge,writeLarge};if(typeof module!=='undefined')module.exports=root.PublicCache;
})(typeof globalThis!=='undefined'?globalThis:this);
