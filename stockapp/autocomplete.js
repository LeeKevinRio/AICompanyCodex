// Shared stock suggestions; no holdings or costs are written here.
function initStockSuggestions(input,onSelect){
 const box=document.createElement('div');box.className='stock-suggestions';box.id=input.id+'-suggestions';box.hidden=true;box.setAttribute('role','listbox');box.setAttribute('aria-label','股票建議');input.parentElement.appendChild(box);input.parentElement.classList.add('suggestion-anchor');
 input.setAttribute('role','combobox');input.setAttribute('aria-autocomplete','list');input.setAttribute('aria-controls',box.id);input.setAttribute('aria-expanded','false');input.setAttribute('autocomplete','off');
 let matches=[],active=-1;
 function close(){box.hidden=true;active=-1;input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant')}
 function draw(){const q=input.value.trim().toUpperCase();if(!q||input.disabled){close();return}const all=new Map(companyCatalog.map(c=>[c.id,c]));for(const s of stocks)if(!['t00','o00'].includes(s.id)&&!all.has(s.id))all.set(s.id,s);
 matches=[...all.values()].filter(s=>[s.id,s.name,s.fullName].some(v=>String(v||'').toUpperCase().includes(q))).sort((a,b)=>{const rank=s=>s.id===q?0:s.id.startsWith(q)?1:s.name===q?2:s.name.startsWith(q)?3:4;return rank(a)-rank(b)||a.id.localeCompare(b.id)}).slice(0,8);active=-1;
 box.innerHTML=matches.length?matches.map((s,i)=>`<div role="option" id="${box.id}-${i}" data-index="${i}" aria-selected="false"><span><strong>${escape(s.id)}</strong> ${escape(s.name)}</span><small>${s.exchange==='tse'?'上市':s.exchange==='otc'?'上櫃':'商品／待確認'}</small></div>`).join(''):'<p class="muted small">'+(classificationLoading?'股票目錄讀取中，仍可輸入完整代碼。':'找不到建議，可輸入完整代碼查詢。')+'</p>';box.hidden=false;input.setAttribute('aria-expanded','true');
 }
 function choose(i){const s=matches[i];if(!s)return;input.value=s.id;close();onSelect(s)}
 input.addEventListener('input',draw);input.addEventListener('focus',draw);
 input.addEventListener('keydown',e=>{if(e.isComposing)return;if(e.key==='Escape'){e.preventDefault();e.stopPropagation();close();return}if(e.key==='Tab'){close();return}if(box.hidden)return;if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();if(!matches.length)return;active=(active+(e.key==='ArrowDown'?1:-1)+matches.length)%matches.length;[...box.querySelectorAll('[role=option]')].forEach((el,i)=>el.setAttribute('aria-selected',String(i===active)));input.setAttribute('aria-activedescendant',box.id+'-'+active);box.children[active].scrollIntoView({block:'nearest'});}if(e.key==='Enter'&&matches.length){e.preventDefault();e.stopImmediatePropagation();choose(active<0?0:active)}});
 box.addEventListener('mousedown',e=>e.preventDefault());box.addEventListener('click',e=>{const row=e.target.closest('[data-index]');if(row)choose(Number(row.dataset.index))});input.addEventListener('blur',close);document.addEventListener('click',e=>{if(!input.parentElement.contains(e.target))close()});$('editor').addEventListener('close',close);
 return {close};
}
