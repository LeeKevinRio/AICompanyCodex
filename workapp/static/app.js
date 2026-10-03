const $ = (id) => document.getElementById(id);
let view = 'search', page = 1, total = 0, searching = false, pendingFilters = null, displayedFilters = null;
const remoteNames = {any:'不限模式', remote:'全遠端', hybrid:'混合辦公', onsite:'現場辦公', unknown:'模式未明列'};
const time = (value) => value ? new Date(typeof value === 'number' ? value * 1000 : value).toLocaleString('zh-TW', {month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}) : '尚未執行';
function el(tag, cls, text) { const node = document.createElement(tag); if (cls) node.className = cls; if (text !== undefined) node.textContent = text; return node; }
function status(id, message = '', error = false) { $(id).textContent = message; $(id).className = 'status' + (error ? ' error' : ''); }
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || '操作未完成，請稍後再試');
  return data;
}
function filters() {
  return {sources:Array.from(document.querySelectorAll('[name="job-source"]:checked')).map(n=>n.value),keyword:$('keyword').value.trim(),region:$('region').value,remote:$('remote').value,location:$('location').value.trim(),salary_min:Number($('salary-min').value || 0),salary_unit:$('salary-unit').value,include_unknown:$('include-unknown').checked};
}
function describe(f) {
  const parts = [f.keyword || '所有關鍵字', f.region === 'taiwan' ? '台灣可應徵' : '全球', remoteNames[f.remote]];
  if (f.location) parts.push(f.location);
  if (f.salary_min) parts.push(`${f.salary_unit} ${Number(f.salary_min).toLocaleString()} 以上${f.include_unknown ? '（含未公開薪資）' : ''}`);
  if (f.sources) parts.push('來源：'+f.sources.join('、'));
  return parts.join(' · ');
}
function renderExternalSearch() {
  const f = filters();
  const words = f.keyword.split(/[,，]/).map(w=>w.trim()).filter(Boolean);
  const quoted = words.map(w=>'"'+w.replace(/["\\]/g,' ')+'"');
  const keyword = quoted.length > 1 ? '('+quoted.join(' OR ')+')' : (quoted[0] || '');
  const mode = {remote:'("全遠端" OR "完全遠端" OR "fully remote")',hybrid:'("混合辦公" OR "部分遠端" OR hybrid)',onsite:'("現場辦公" OR "on-site")'}[f.remote] || '';
  const links = [];
  for (const [name, domain, base, parameter] of [
    ['104','104.com.tw/job/','https://www.104.com.tw/jobs/search/','keyword'],
    ['1111','1111.com.tw/job/','https://www.1111.com.tw/search/job','ks']
  ]) {
    const direct = new URL(base); direct.searchParams.set(parameter,words.join(' '));
    const google = new URL('https://www.google.com/search');
    google.searchParams.set('q',[`site:${domain}`,keyword,f.location,mode].filter(Boolean).join(' '));
    for (const [label,url] of [[`${name} 站內搜尋`,direct],[`Google 搜尋 ${name}`,google]]) {
      const a = el('a','outline',label+' ↗'); a.href=url.href; a.target='_blank'; a.rel='noopener noreferrer'; links.push(a);
    }
  }
  $('external-links').replaceChildren(...links);
  $('external-context').textContent = (f.keyword || '所有職缺')+' · '+remoteNames[f.remote]+'｜站內搜尋僅帶入關鍵字，其餘條件請在原站設定。';
}
let taiwanRequest = 0;
let directRequest = 0;
function clearDirectResults() {
  directRequest++;
  $('direct-jobs').replaceChildren();
  $('direct-status').textContent = '條件已變更，請重新搜尋 104。';
  $('search-104').disabled = false;
}
async function search104() {
  if (!$('search-form').reportValidity()) return;
  const request = ++directRequest;
  $('search-104').disabled = true;
  $('direct-jobs').replaceChildren();
  $('direct-status').textContent = '正在讀取 104，可能需要約一分鐘…';
  try {
    const data = await api('/api/search104', filters());
    if (request !== directRequest) return;
    renderJobs('direct-jobs',data.results);
    $('direct-status').textContent = data.state === 'ready' ? `${data.results.length} 筆符合條件／本次讀取 ${data.fetched_count} 筆 · ${data.cached ? '快取' : '取得'} ${time(data.fetched_at)}；非全站總數。` : data.message;
    if (data.stale) $('direct-status').textContent += ` 顯示上次資料 ${time(data.fetched_at)}。`;
  } catch(error) { if(request===directRequest) $('direct-status').textContent=error.message; }
  finally { if(request===directRequest) $('search-104').disabled=false; }
}
function clearTaiwanResults() {
  clearDirectResults();
  taiwanRequest++;
  $('taiwan-jobs').replaceChildren();
  $('taiwan-status').textContent = '條件已變更，請重新搜尋 104／1111。';
  $('search-taiwan').disabled = false;
}
async function searchTaiwan() {
  if (!$('search-form').reportValidity()) return;
  const request = ++taiwanRequest;
  $('search-taiwan').disabled = true;
  $('taiwan-status').textContent = '正在搜尋 104／1111…';
  $('taiwan-jobs').replaceChildren();
  try {
    const data = await api('/api/web-search',filters());
    if (request !== taiwanRequest) return;
    $('search-setup').open = data.state === 'not_configured';
    $('taiwan-status').textContent = data.state !== 'ready' ? data.message : `${data.results.length} 筆搜尋線索 · ${data.cached ? '快取' : '取得'} ${time(data.fetched_at)}${data.results.length ? '' : '；不代表兩站沒有相關職缺。'}`;
    if (data.stale && data.results.length) $('taiwan-status').textContent += ` 顯示上次結果（${time(data.fetched_at)}）。`;
    $('taiwan-jobs').replaceChildren(...data.results.map(job=>{
      const card = el('article','search-lead');
      const title = el('h3'), link = el('a','',job.title);
      link.href = job.url; link.target = '_blank'; link.rel = 'noopener noreferrer'; title.append(link);
      card.append(el('span','pill',job.source+' · Google 收錄 · 招募狀態待確認'),title,el('p','',job.description || '搜尋未提供摘要，請查看原始職缺。'));
      return card;
    }));
  } catch(error) {
    if (request === taiwanRequest) $('taiwan-status').textContent = error.message;
  } finally { if (request === taiwanRequest) $('search-taiwan').disabled = false; }
}
function empty(target, title, message) {
  const node = el('div','empty'); node.append(el('strong','',title), el('p','small',message)); $(target).replaceChildren(node);
}
function jobCard(job) {
  const card = el('article','job');
  card.append(el('div','company-icon', Array.from(job.company)[0] || 'W'));
  const content = el('div'); const head = el('div','job-head'); const text = el('div');
  const title = el('h3'); const link = el('a','',job.title);
  if (/^https?:\/\//i.test(job.url)) { link.href = job.url; link.target = '_blank'; link.rel = 'noopener noreferrer'; }
  title.append(link); text.append(title,el('p','job-company',job.company)); head.append(text,el('span','job-source',job.source_name)); content.append(head);
  const meta = el('div','job-meta');
  meta.append(el('span','pill',job.location),el('span','pill' + (job.remote === 'remote' ? ' remote' : ''),remoteNames[job.remote] || '模式未明列'));
  if (job.active === false) meta.append(el('span','pill','來源已不再列出'));
  content.append(meta);
  const bottom = el('div','job-bottom');
  bottom.append(el('span','job-salary',job.salary), el('span','job-date',job.discovered_at ? `首次發現 ${time(job.discovered_at)}` : job.published ? `發布／更新 ${time(job.published)}` : '發布日期未明列'));
  content.append(bottom);
  if (job.imported_at) content.append(el('p','small muted',`手動匯入 ${time(job.imported_at)} · 非即時資料，應徵前請確認原站`));
  else if (job.read_at) content.append(el('p','small muted',`瀏覽器讀取 ${time(job.read_at)} · 列表摘要，完整條件請確認原站`));
  const details = el('details'); details.append(el('summary','','查看工作內容'),el('p','',job.description || '請到原始招募頁面查看完整說明。')); content.append(details);
  card.append(content); return card;
}
function renderJobs(target, jobs) { $(target).replaceChildren(...jobs.map(jobCard)); }
function renderSources(sources) {
  $('sources').replaceChildren(...sources.map(s => {
    const card = el('div','source' + (s.error ? ' error' : ''));
    card.append(el('strong','',s.name),el('p','',s.last_success ? `${s.count} 個職缺 · 更新 ${time(s.last_success)}` : '尚未取得自動搜尋資料'));
    if (s.note) card.append(el('p','',s.note));
    if (s.coverage?.pages !== undefined) card.append(el('p','',`已讀 ${s.coverage.pages} 頁、${s.coverage.detail_pages || 0} 筆詳細內容。${s.coverage.queries!==undefined ? `${s.coverage.finished_queries}/${s.coverage.queries} 組查詢到達結尾。` : ''}${s.coverage.message}`));
    if (s.matched !== undefined) card.append(el('p','',`符合 ${s.matched} 筆；排除：${Object.entries(s.excluded || {}).map(([k,v])=>`${k} ${v}`).join('、') || '無'}（依序計算，不重複計數）`));
    if (s.error) card.append(el('p','',`讀取失敗，保留上次資料：${s.error}`));
    else if (s.state !== 'skipped') card.append(el('p','',`最快每 ${s.refresh_minutes} 分鐘更新`));
    return card;
  }));
}
async function search(newPage = 1, continueSearch = false) {
  if (searching) return;
  if (!filters().sources.length) {status('search-status','請至少選擇一個職缺來源。',true);return;}
  searching = true; $('search-button').disabled = true; $('continue-search').disabled=true;
  status('search-status','正在逐頁搜尋，台灣與全球分開查詢；LinkedIn 最多約 150 秒…');
  const f = newPage === 1 || !displayedFilters ? filters() : displayedFilters;
  try {
    const data = await api('/api/search', {...f,page:newPage,continue_search:continueSearch});
    page = data.page; total = data.total; displayedFilters = f;
    const failed = data.sources.filter(s=>s.error);
    $('coverage-summary').replaceChildren(...data.sources.map(s=>{
      const card=el('div','source'+(s.error?' error':''));
      card.append(el('strong','',s.name),el('p','',s.state==='skipped' ? '尚未查詢' : s.error && !s.count ? '讀取未完成，無法判定職缺數量' : `已保存 ${s.count} 筆 · 符合 ${s.matched ?? data.jobs.filter(j=>j.source===s.id).length} 筆`));
      if(s.note)card.append(el('p','small',s.note));
      if(s.error)card.append(el('p','small','搜尋尚未完整，請查看下方來源原因。'));
      if(s.coverage?.unverified_details)card.append(el('p','small',`${s.coverage.unverified_details} 筆內文待確認，可能還有符合職缺。`));
      return card;
    }));
    $('result-count').textContent = !total && failed.length ? '未完整取得' : total.toLocaleString();
    $('result-context').textContent = `${f.region === 'taiwan' ? '台灣優先' : '台灣職缺優先列出'} · 職稱符合優先 · 以下是已取得結果，非市場總數`;
    renderJobs('jobs',data.jobs);
    if (!data.jobs.length) empty('jobs',failed.length ? '搜尋未完成，不能判定沒有職缺' : '已取得資料中沒有符合條件的職缺',failed.length ? '部分來源未能讀取。104 可使用上方「備用搜尋與接入說明」匯入已開啟的搜尋頁。' : '試試其他關鍵字、放寬薪資條件，或改選全球職缺。資料來源的覆蓋範圍有限。');
    renderSources(data.sources);
    status('search-status',failed.length ? '部分來源讀取失敗，以下可能包含前次資料。請查看下方來源狀態。' : '',Boolean(failed.length));
    $('pagination').hidden = total <= 30;
    $('previous').disabled = page <= 1; $('next').disabled = page * 30 >= total;
    $('page-label').textContent = `${page} / ${Math.max(1,Math.ceil(total/30))}`;
  } catch (error) { status('search-status',error.message,true); }
  finally { searching = false; $('search-button').disabled = false; $('continue-search').disabled=false; }
}
function setView(next) {
  view = next; $('search-view').hidden = next !== 'search'; $('monitor-view').hidden = next !== 'monitor';
  document.querySelectorAll('[data-view]').forEach(b=>{b.classList.toggle('active',b.dataset.view===next); if (b.dataset.view===next) b.setAttribute('aria-current','page'); else b.removeAttribute('aria-current');});
  if (next === 'monitor') loadRules();
}
async function ruleAction(button, path, body, message) {
  button.disabled = true; status('monitor-status',message);
  try {
    const result = await api(path,body);
    if (path === '/api/scan') status('monitor-status',`掃描完成：${result.matches} 個符合條件，${result.new_count} 個首次發現。${result.warnings.length ? '部分來源讀取失敗，已保留上次資料。' : ''}`,Boolean(result.warnings.length));
    else status('monitor-status','');
    await loadRules();
  } catch (error) { status('monitor-status',error.message,true); }
  finally { button.disabled = false; }
}
function ruleCard(rule) {
  const card = el('article','rule'), heading = el('div','rule-heading');
  heading.append(el('h3','',rule.name),el('span','rule-state'+(rule.paused?' paused':''),rule.paused?'已暫停':`每 ${rule.hours} 小時`));
  card.append(heading,el('p','rule-summary',describe(rule.filters)));
  const stats = el('div','rule-stats');
  for (const [name,value] of [['已發現',`${rule.discovered_count} 個`],['上次掃描',time(rule.last_run)],['下次掃描',rule.paused ? '已暫停' : time(rule.next_run)]]) {
    const part = el('div','',name+' '); part.append(el('strong','',value)); stats.append(part);
  }
  card.append(stats);
  if (rule.latest?.warnings?.length) card.append(el('p','rule-warning','最近掃描有來源讀取失敗，結果可能不完整。'));
  const actions = el('div','rule-actions');
  const run = el('button','outline','立即掃描'); run.onclick=()=>ruleAction(run,'/api/scan',{id:rule.id},'正在掃描，請稍候…');
  const pause = el('button','outline',rule.paused ? '恢復掃描' : '暫停'); pause.onclick=()=>ruleAction(pause,'/api/rules/pause',{id:rule.id,paused:!rule.paused},'正在更新掃描狀態…');
  const results = el('button','outline','查看已發現職缺'); results.onclick=async()=>{
    results.disabled=true;
    try {
      const data=await api('/api/discoveries?rule_id='+rule.id);
      $('discoveries-section').hidden=false; $('discoveries-title').textContent=rule.name+' · 已發現職缺'; renderJobs('discoveries',data.jobs);
      if (!data.jobs.length) empty('discoveries','還沒有發現職缺','等待首次掃描，或點選「立即掃描」。');
      $('discoveries-section').scrollIntoView({behavior:'smooth',block:'start'});
    } catch(error) {status('monitor-status',error.message,true);} finally {results.disabled=false;}
  };
  const remove = el('button','text-button','刪除'); remove.onclick=()=>{
    if (confirm(`刪除「${rule.name}」與這組條件的掃描紀錄？`)) {
      $('discoveries-section').hidden=true;
      ruleAction(remove,'/api/rules/delete',{id:rule.id},'正在刪除掃描條件…');
    }
  };
  actions.append(run,results,pause,remove); card.append(actions); return card;
}
async function loadRules() {
  try {
    const data=await api('/api/rules'); $('rule-count').textContent=data.rules.length;
    $('rules').replaceChildren(...data.rules.map(ruleCard));
    if (!data.rules.length) empty('rules','你的雷達，還沒有設定條件','先搜尋工作，再點選「儲存為自動掃描」。');
  } catch(error) {status('monitor-status',error.message,true);}
}
function openSave() {
  if (!$('search-form').reportValidity()) return;
  pendingFilters=filters(); $('save-summary').textContent=describe(pendingFilters);
  $('rule-name').value=pendingFilters.keyword ? `${pendingFilters.keyword} · ${pendingFilters.region==='taiwan'?'台灣':'全球'}`.slice(0,80) : '';
  status('save-error'); $('save-dialog').showModal(); $('rule-name').focus();
}
$('search-form').addEventListener('submit',event=>{event.preventDefault();search();});
$('search-form').addEventListener('input',renderExternalSearch);
$('search-form').addEventListener('change',renderExternalSearch);
$('search-form').addEventListener('input',clearTaiwanResults);
$('search-form').addEventListener('change',clearTaiwanResults);
$('search-taiwan').onclick=searchTaiwan;
$('search-104').onclick=search104;
let browser104Polling = null;
async function pollBrowser104() {
  try {
    const result=await api('/api/104/browser');
    const active=['starting','loading','reading','waiting_user'].includes(result.state);
    $('browser104-start').disabled=active; $('browser104-resume').disabled=active; $('browser104-stop').disabled=!active;
    if(result.state!=='idle') status('browser104-status',`${result.keyword} · 已讀 ${result.pages} 頁 · ${result.count} 筆／網站 ${result.total ?? '未知'} 筆。${result.message}`,['error','partial','waiting_user'].includes(result.state));
    if(active) browser104Polling=setTimeout(pollBrowser104,2000);
    else {browser104Polling=null; if(result.state!=='idle') status('browser104-status',$('browser104-status').textContent+' 按「搜尋工作」套用目前篩選。');}
  } catch(error) {browser104Polling=null;status('browser104-status',error.message,true);$('browser104-start').disabled=false;$('browser104-resume').disabled=false;}
}
async function startBrowser104(resume) {
  $('browser104-start').disabled=true; $('browser104-resume').disabled=true;
  try {await api('/api/104/browser/start',{keyword:filters().keyword,resume}); if(browser104Polling)clearTimeout(browser104Polling);await pollBrowser104();}
  catch(error){status('browser104-status',error.message,true);$('browser104-start').disabled=false;$('browser104-resume').disabled=false;}
}
$('browser104-start').onclick=()=>startBrowser104(false);
$('browser104-resume').onclick=()=>startBrowser104(true);
$('browser104-stop').onclick=async()=>{try{await api('/api/104/browser/stop',{});status('browser104-status','正在停止，已讀結果會保留。');}catch(error){status('browser104-status',error.message,true);}};
pollBrowser104();
let import104Html = '';
function prepare104(html) {
  import104Html = html;
  $('import104').disabled = !html;
  status('import104-status', html ? '已接收網頁內容，按「匯入職缺」後儲存。' : '沒有網頁格式；請重新複製搜尋結果，或選擇 HTML 檔案。', !html);
}
$('paste104').addEventListener('paste', event => {
  event.preventDefault();
  prepare104(event.clipboardData.getData('text/html'));
  $('paste104').value = import104Html ? '已接收網頁內容（不會執行其中的程式）' : '';
});
$('paste104').addEventListener('input',()=>prepare104(''));
$('file104').addEventListener('change',async event=>{
  prepare104('');
  const file = event.target.files[0];
  if (!file) return;
  if (file.size>2000000) return status('import104-status','檔案超過 2 MB，請改用複製搜尋頁內容。',true);
  try {prepare104(await file.text());} catch {status('import104-status','檔案讀取失敗，請重新選擇。',true);}
});
$('import104').onclick=async()=>{
  $('import104').disabled=true;
  try {
    const result=await api('/api/import104',{html:import104Html});
    import104Html=''; $('paste104').value=''; $('file104').value='';
    status('import104-status',`已匯入／更新 ${result.imported} 筆，共保存 ${result.total} 筆快照。請搜尋工作套用條件；快照不會自動更新。`);
  } catch(error) {status('import104-status',error.message,true);}
  finally {$('import104').disabled=!import104Html;}
};
$('continue-search').onclick=()=>search(1,true);
$('previous').onclick=()=>search(page-1); $('next').onclick=()=>search(page+1);
$('reset-filters').onclick=()=>{$('search-form').reset();renderExternalSearch();clearTaiwanResults();search();};
$('open-save').onclick=openSave; $('cancel-save').onclick=()=>$('save-dialog').close();
$('new-rule').onclick=()=>{setView('search');$('keyword').focus();};
$('close-discoveries').onclick=()=>{$('discoveries-section').hidden=true;};
document.querySelectorAll('[data-view]').forEach(button=>button.onclick=()=>setView(button.dataset.view));
$('save-form').addEventListener('submit',async event=>{
  event.preventDefault(); $('save-button').disabled=true; status('save-error');
  try {
    await api('/api/rules',{name:$('rule-name').value.trim(),hours:Number($('rule-hours').value),filters:pendingFilters});
    $('save-dialog').close(); setView('monitor'); status('monitor-status','條件已儲存，後端會在 30 秒內執行首次掃描。');
  } catch(error) {status('save-error',error.message,true);} finally {$('save-button').disabled=false;}
});
renderExternalSearch(); search(); loadRules();
setInterval(async()=>{
  if (document.visibilityState==='hidden') return;
  if (view==='monitor' && !document.querySelector('.rule button:disabled')) await loadRules();

},30000);
