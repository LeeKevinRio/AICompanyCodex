const BASE='http://127.0.0.1:8001';
let token='', running=false, polling=false, timer=null;
const active=new Set();
const status=document.getElementById('status');
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function log(message){const li=document.createElement('li');li.textContent=message;document.getElementById('log').prepend(li);}
async function request(path,body){
  const response=await fetch(BASE+'/api/browser-helper/'+path,{signal:AbortSignal.timeout(10000),method:body?'POST':'GET',headers:{Authorization:'Bearer '+token,...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
  const data=await response.json();if(!response.ok)throw new Error(data.error||'連線失敗');return data;
}
// Executed only in the task's public search page. No storage/cookie access.
function readCards(source){
  const selector=source==='cake'?"a[class*='jobTitle'][href*='/companies/'][href*='/jobs/']":'div.job_seen_beacon, a.tapItem';
  const cards=Array.from(document.querySelectorAll(selector));
  const roots=source==='cake'?cards.map(a=>{let p=a;for(let i=0;i<6;i++){p=p.parentElement;if(!p)break;if(/JobSearchItem.*content/.test(p.className))return p;}return a.closest('article')||a.parentElement;}):cards.map(c=>c.closest('.cardOutline')||c);
  const html=roots.map(root=>{const copy=root.cloneNode(true);copy.querySelectorAll('script,style,iframe,input,textarea,form,button').forEach(n=>n.remove());
    for(const el of [copy,...copy.querySelectorAll('*')])for(const attr of [...el.attributes])if(!['class','href','data-testid'].includes(attr.name))el.removeAttribute(attr.name);
    return copy.outerHTML;
  }).join('');
  return {html:html.slice(0,2000000),count:cards.length,challenge:/just a moment|captcha|verify|security check|請稍候|安全驗證/i.test(document.title)};
}
async function processTask(task){
  const allowed={cake:['www.cake.me'],indeed:['www.indeed.com','tw.indeed.com']};
  const url=new URL(task.url);
  if(url.protocol!=='https:'||!allowed[task.source]?.includes(url.hostname)||url.pathname!=='/jobs')throw new Error('非允許的搜尋網址');
  let tab;
  try{
    tab=await chrome.tabs.create({url:task.url,active:false});
    log(task.source+'：開始讀取');const started=Date.now();let last='',stable=0;
    while(running&&Date.now()-started<60000){
      await pause(1000);
      if(!running)break;
      let result;
      try{[result]=await chrome.scripting.executeScript({target:{tabId:tab.id},func:readCards,args:[task.source]});}catch{continue;}
      const data=result?.result;if(!data)continue;
      if(data.count){stable=data.html===last?stable+1:0;last=data.html;if(stable>=1){await request('result',{id:task.id,html:data.html});log(task.source+'：已送回 '+data.count+' 張卡片');return;}}
      else if(data.challenge)status.textContent=task.source+' 正在驗證，請查看原站分頁；完成後自動繼續。';
    }
    throw new Error(running?'一般瀏覽器尚未載入職缺，可能需要在原站完成驗證':'助手已停止');
  }catch(error){await request('result',{id:task.id,error:error.message});log(task.source+'：'+error.message);}
  finally{if(tab)await chrome.tabs.remove(tab.id).catch(()=>{});}
}
async function poll(){
  if(!running||polling||active.size>=2)return;
  polling=true;
  try{const {task}=await request('poll');status.textContent='已連線 · '+active.size+' 個讀取工作';if(task){active.add(task.id);processTask(task).catch(e=>log(e.message)).finally(()=>active.delete(task.id));}}
  catch(error){status.textContent=error.message;}
  finally{polling=false;}
}
document.getElementById('connect').onclick=async()=>{
  token=document.getElementById('token').value.trim();if(!token)return;
  running=true;document.getElementById('connect').disabled=true;document.getElementById('disconnect').disabled=false;
  await poll();timer=setInterval(poll,3000);
};
document.getElementById('disconnect').onclick=async()=>{
  running=false;clearInterval(timer);document.getElementById('disconnect').disabled=true;
  // Let any already-sent poll finish before clearing the server heartbeat.
  while(polling)await pause(100);
  try{await request('disconnect',{});}catch(error){log(error.message);}
  while(active.size)await pause(100);
  status.textContent='已停止';document.getElementById('connect').disabled=false;
};
