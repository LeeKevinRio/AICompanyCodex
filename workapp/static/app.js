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
  return {keyword:$('keyword').value.trim(),region:$('region').value,remote:$('remote').value,location:$('location').value.trim(),salary_min:Number($('salary-min').value || 0),salary_unit:$('salary-unit').value,include_unknown:$('include-unknown').checked};
}
function describe(f) {
  const parts = [f.keyword || '所有關鍵字', f.region === 'taiwan' ? '台灣可應徵' : '全球', remoteNames[f.remote]];
  if (f.location) parts.push(f.location);
  if (f.salary_min) parts.push(`${f.salary_unit} ${Number(f.salary_min).toLocaleString()} 以上${f.include_unknown ? '（含未公開薪資）' : ''}`);
  return parts.join(' · ');
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
  bottom.append(el('span','job-salary',job.salary), el('span','job-date',job.discovered_at ? `首次發現 ${time(job.discovered_at)}` : `發布／更新 ${time(job.published)}`));
  content.append(bottom);
  const details = el('details'); details.append(el('summary','','查看工作內容'),el('p','',job.description || '請到原始招募頁面查看完整說明。')); content.append(details);
  card.append(content); return card;
}
function renderJobs(target, jobs) { $(target).replaceChildren(...jobs.map(jobCard)); }
function renderSources(sources) {
  $('sources').replaceChildren(...sources.map(s => {
    const card = el('div','source' + (s.error ? ' error' : ''));
    card.append(el('strong','',s.name),el('p','',`${s.count} 個職缺 · 更新 ${time(s.last_success)}`));
    if (s.error) card.append(el('p','',`讀取失敗，保留上次資料：${s.error}`));
    else card.append(el('p','',`最快每 ${s.refresh_minutes} 分鐘更新`));
    return card;
  }));
}
async function search(newPage = 1) {
  if (searching) return;
  searching = true; $('search-button').disabled = true;
  status('search-status','正在讀取招募來源與篩選職缺…');
  const f = newPage === 1 || !displayedFilters ? filters() : displayedFilters;
  try {
    const data = await api('/api/jobs?' + new URLSearchParams({...f,page:newPage}));
    page = data.page; total = data.total; displayedFilters = f;
    $('result-count').textContent = total.toLocaleString();
    $('result-context').textContent = `${f.region === 'taiwan' ? '台灣優先' : '台灣職缺優先列出'} · 依發布／更新時間排序`;
    renderJobs('jobs',data.jobs);
    if (!data.jobs.length) empty('jobs','目前沒有符合條件的職缺','試試其他關鍵字、放寬薪資條件，或改選全球職缺。資料來源的覆蓋範圍有限。');
    renderSources(data.sources);
    const failed = data.sources.filter(s=>s.error);
    status('search-status',failed.length ? '部分來源讀取失敗，以下可能包含前次資料。請查看下方來源狀態。' : '',Boolean(failed.length));
    $('pagination').hidden = total <= 30;
    $('previous').disabled = page <= 1; $('next').disabled = page * 30 >= total;
    $('page-label').textContent = `${page} / ${Math.max(1,Math.ceil(total/30))}`;
  } catch (error) { status('search-status',error.message,true); }
  finally { searching = false; $('search-button').disabled = false; }
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
$('previous').onclick=()=>search(page-1); $('next').onclick=()=>search(page+1);
$('reset-filters').onclick=()=>{$('search-form').reset();search();};
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
search(); loadRules();
setInterval(async()=>{
  if (document.visibilityState==='hidden') return;
  if (view==='monitor' && !document.querySelector('.rule button:disabled')) await loadRules();
  try {const data=await api('/api/status');renderSources(data.sources);} catch (_) { /* Search and monitoring show actionable errors on use. */ }
},30000);
