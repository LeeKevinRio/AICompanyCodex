"""Bounded, query-scoped public job searches; no login or challenge bypass."""
import hashlib
import json
import re
import threading
import time
import urllib.request
import urllib.error
from urllib.parse import urlencode, urljoin, urlparse
from bs4 import BeautifulSoup
from .domain import plain_text, salary_fields, matches, keyword_matches

PLATFORMS = {'linkedin':'LinkedIn', 'cake':'Cake', 'indeed':'Indeed', 'remoteok':'RemoteOK'}


def request_text(url, timeout=25):
    request = urllib.request.Request(url, headers={'User-Agent':'WorkApp/0.2 (personal job search)', 'Accept':'text/html,application/json'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode('utf-8')


def job(source, title, company, location, url, description='', salary='', published='', remote=None):
    host = urlparse(url).hostname or ''
    domains = {'linkedin':'linkedin.com','cake':'cake.me','indeed':'indeed.com','remoteok':'remoteok.com'}
    domain = domains[source]
    if urlparse(url).scheme not in ('http','https') or not (host == domain or host.endswith('.'+domain)):
        raise ValueError('職缺連結不屬於資料來源')
    title, location = plain_text(title), plain_text(location)
    if not title: raise ValueError('職缺標題缺失')
    hint = (title+' '+location).lower()
    if remote is None:
        remote = 'hybrid' if re.search(r'hybrid|混合|部分遠端',hint) else 'remote' if re.search(r'\bremote\b|全遠端|完全遠端',hint) else 'unknown'
    local = bool(re.search(r'taiwan|taipei|hsinchu|taichung|kaohsiung|台[灣北中南東]|臺[灣北中南東]|新北|桃園|新竹|高雄',location,re.I))
    eligible = local or bool(re.search(r'worldwide|anywhere|全球',location,re.I))
    return {'id':source+':'+hashlib.sha256(url.encode()).hexdigest()[:24], 'source':source,'source_name':PLATFORMS[source], 'title':title,'company':plain_text(company) or '公司未提供','location':location or '地區未提供','url':url,'description':plain_text(description),'salary':plain_text(salary) or '薪資未公開', **salary_fields(salary), 'published':published, 'remote':remote,'taiwan':eligible,'local_taiwan':local,'tags':''}


def parse_cards(source, html, base):
    soup = BeautifulSoup(html,'html.parser')
    out = []
    def text(card, selector):
        node=card.select_one(selector)
        return node.get_text(' ',strip=True) if node else ''
    if source == 'linkedin':
        for card in soup.select('li'):
            anchor=card.select_one('a.base-card__full-link')
            title=text(card,'h3.base-search-card__title')
            if not anchor or not title: continue
            date=card.select_one('time[datetime]')
            out.append(job(source,title,text(card,'h4.base-search-card__subtitle'),text(card,'.job-search-card__location'),anchor['href'].split('?')[0],salary=text(card,"[class*='salary']"),published=date['datetime'] if date else ''))
    elif source == 'indeed':
        for card in soup.select('div.job_seen_beacon'):
            anchor=card.select_one('a.jcs-JobTitle, h3.jobTitle a, h2.jobTitle a')
            if not anchor: continue
            out.append(job(source,anchor.get_text(' ',strip=True),text(card,"[data-testid='company-name'], .companyName"),text(card,"[data-testid='text-location'], .companyLocation"),urljoin(base,anchor['href']),description=text(card,'.job-snippet'),salary=text(card,"[data-testid*='salary'], [class*='salary-snippet']")))
    else:
        for anchor in soup.select("a[class*='jobTitle'][href*='/companies/'][href*='/jobs/']"):
            card=anchor
            for _ in range(6):
                card=card.parent
                if card is None: break
                if any('JobSearchItem' in c and 'content' in c for c in card.get('class',[])): break
            card=card or anchor.parent
            out.append(job(source,anchor.get_text(' ',strip=True),text(card,"[class*='companyName']"),text(card,"[class*='features']"),urljoin(base,anchor['href']).split('?')[0],salary=text(card,"[class*='salary']")))
    if not out:
        # Empty shell / CAPTCHA / changed selectors must not become a false zero.
        raise ValueError('沒有取得可辨識的職缺卡片，可能無結果、頁面改版或需要驗證')
    return list({j['url']:j for j in out}.values())


def linkedin_plan(filters):
    terms=[s.strip() for s in re.split('[,，]',filters['keyword']) if s.strip()]
    expanded=[]
    for term in terms:
        expanded.extend(['Unity','Unity3D','U3D'] if term.casefold() in ('unity','unity3d','unity engine','u3d') else [term])
    locations=[filters['location']] if filters['location'] else (['Taiwan'] if filters['region']=='taiwan' else ['Taiwan','Worldwide'])
    return [(term,location) for term in dict.fromkeys(expanded) for location in locations]


def fetch_linkedin(filters, reader=request_text, sleep=time.sleep, clock=time.monotonic, max_pages=24, max_seconds=90):
    # Round-robin avoids spending the entire budget on a single location/alias.
    queries=[{'keyword':k,'location':l,'offset':0,'done':False} for k,l in linkedin_plan(filters)]
    previous={j['id']:j for j in filters.get('_previous_jobs',[])}
    found={};pages=0;stop='';started=clock();attempts=0
    while queries and not all(q['done'] for q in queries):
        for q in queries:
            if q['done']: continue
            if pages>=max_pages or clock()-started>=max_seconds:
                stop='已達本次讀取上限，尚未查完';break
            if attempts: sleep(1.2)
            attempts+=1
            url='https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?'+urlencode({'keywords':q['keyword'],'location':q['location'],'start':q['offset']})
            try:
                html=reader(url,timeout=min(15,max(1,max_seconds-(clock()-started))))
                pages+=1
                if not html.strip(): q['done']=True;continue
                rows=parse_cards('linkedin',html,'https://www.linkedin.com')
                before=len(found)
                for row in rows:
                    # One job may appear under different country subdomains/slugs.
                    match=re.search(r'(\d{6,})/?$',urlparse(row['url']).path)
                    if match:
                        row['url']='https://www.linkedin.com/jobs/view/'+match[1]
                        row['id']='linkedin:'+match[1]
                    old=previous.get(row['id'])
                    if old and old.get('description'): row['description']=old['description']
                    found[row['id']]=row
                # Offsets advance by the returned page size, not a hardcoded 25.
                q['offset']+=len(rows)
                signature=tuple(sorted(r['id'] for r in rows))
                if signature==q.get('last'): q['done']=True
                q['last']=signature
            except urllib.error.HTTPError as exc:
                stop='來源限制請求（HTTP %s），已保留讀到的職缺'%exc.code;break
            except Exception:
                stop='後續頁面未能讀取或格式改變，已保留讀到的職缺';break
        if stop: break
    detail_pages=0;detail_failures=0;detail_started=clock()
    terms=[t.strip().casefold() for t in re.split('[,，]',filters['keyword']) if t.strip()]
    candidates=[r for r in found.values() if not r.get('description') and not any(keyword_matches((r['title']+' '+r['company']).casefold(),t) for t in terms)]
    for row in candidates[:40]:
        if clock()-detail_started>=60: break
        identifier=row['id'].split(':')[-1]
        if not identifier.isdigit(): continue
        sleep(1.2)
        try:
            html=reader('https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/'+identifier,timeout=min(10,max(1,60-(clock()-detail_started))))
            soup=BeautifulSoup(html,'html.parser')
            desc=soup.select_one('.show-more-less-html__markup, .description__text')
            if not desc: raise ValueError('未取得描述')
            row['description']=desc.get_text(' ',strip=True);detail_pages+=1
        except Exception:
            detail_failures+=1
            break  # Do not keep sending requests when the site rejects details.
    unresolved=len(candidates)-detail_pages
    if unresolved: stop=(stop+'；' if stop else '')+f'{unresolved} 筆工作內容尚未確認，可能漏掉只在內文提到技能的職缺'
    return {'jobs':list(found.values()),'coverage':{'pages':pages,'detail_pages':detail_pages,'unverified_details':unresolved,'queries':len(queries),'finished_queries':sum(q['done'] for q in queries),'limited':bool(stop),'message':stop or '目前查詢已讀到結尾；仍非全網職缺總數'}}


def filter_summary(jobs, filters):
    remaining=list(jobs);reasons={}
    neutral=dict(filters,region='global',remote='any',location='',keyword='',salary_min=0)
    for key,label in [('keyword','關鍵字'),('region','應徵地區'),('location','地點'),('remote','工作模式'),('salary_min','薪資')]:
        trial=neutral|{key:filters[key]}
        kept=[j for j in remaining if matches(j,trial)]
        if len(remaining)!=len(kept): reasons[label]=len(remaining)-len(kept)
        remaining=kept
    return remaining,reasons


def fetch_platform(source, filters):
    keyword=filters['keyword']
    location=filters['location'] or ('Taiwan' if filters['region']=='taiwan' else '')
    if source=='remoteok':
        rows=json.loads(request_text('https://remoteok.com/api'))
        if not isinstance(rows,list): raise ValueError('RemoteOK 格式不完整')
        out=[]
        for row in rows:
            if not isinstance(row,dict) or not row.get('id'): continue
            salary=''  # Feed numeric salary lacks an explicit currency/period contract here.
            out.append(job(source,row.get('position',''),row.get('company',''),row.get('location') or '',row.get('url') or '',row.get('description',''),salary,str(row.get('date') or ''),remote='remote'))
        return out
    if source=='linkedin':
        return fetch_linkedin(filters)
    from playwright.sync_api import sync_playwright
    base='https://www.cake.me' if source=='cake' else ('https://tw.indeed.com' if filters['region']=='taiwan' else 'https://www.indeed.com')
    url=base+'/jobs?'+urlencode({'q':keyword,'page':1} if source=='cake' else {'q':keyword,'l':location,'start':0})
    selector="a[class*='jobTitle'][href*='/companies/'][href*='/jobs/']" if source=='cake' else 'div.job_seen_beacon'
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            page=browser.new_page(locale='zh-TW')
            response=page.goto(url,wait_until='domcontentloaded',timeout=30000)
            if response is None or response.status >= 400: raise ValueError('來源拒絕連線')
            if re.search(r'just a moment|captcha|verify',page.title(),re.I): raise ValueError('來源要求驗證')
            page.wait_for_selector(selector,timeout=15000)
            return parse_cards(source,page.content(),base)
        finally: browser.close()


class PlatformSearch:
    def __init__(self,db,fetcher=fetch_platform,clock=time.time):
        self.db,self.fetcher,self.clock=db,fetcher,clock
        self.locks={k:threading.Lock() for k in PLATFORMS}
        with db() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS platform_cache(source TEXT, query TEXT, payload TEXT, fetched_at REAL, attempted_at REAL, error TEXT, PRIMARY KEY(source,query))')
            if 'coverage' not in [r[1] for r in conn.execute('PRAGMA table_info(platform_cache)')]:
                conn.execute("ALTER TABLE platform_cache ADD COLUMN coverage TEXT NOT NULL DEFAULT '{}'")

    def search(self,source,filters, resume=False):
        query=json.dumps({k:filters[k] for k in ('keyword','region','location')},sort_keys=True)
        if source=='remoteok': query='feed'
        elif source=='linkedin': query='v3:'+query
        status={'id':source,'name':PLATFORMS[source],'count':0,'last_success':None,'error':None,'refresh_minutes':360 if source=='remoteok' else 30,'note':('台灣／全球分開查詢、別名與分頁；非全站總數' if source=='linkedin' else '公開搜尋第一頁；非全站職缺') if source!='remoteok' else '公開職缺 feed；地區未知不推定台灣可應徵'}
        if source!='remoteok' and not filters['keyword']:
            return [],status|{'note':'未查詢：請輸入關鍵字','state':'skipped'}
        if source not in ('remoteok','linkedin') and re.search('[,，]',filters['keyword']):
            return [],status|{'error':'此來源每次請使用一個關鍵字','state':'skipped'}
        with self.locks[source]:
            now=self.clock()
            with self.db() as conn:
                row=conn.execute('SELECT * FROM platform_cache WHERE source=? AND query=?',(source,query)).fetchone()
            jobs=json.loads(row['payload']) if row else []
            fetched=row['fetched_at'] if row else None
            error=row['error'] if row else None
            coverage=json.loads(row['coverage']) if row else {}
            interval=21600 if source=='remoteok' else (300 if error else 1800)
            if not row or now-row['attempted_at']>=interval or (resume and source=='linkedin' and now-row['attempted_at']>=60):
                try:
                    incoming=self.fetcher(source,filters|{'_previous_jobs':jobs})
                    metadata=incoming.get('coverage',{}) if isinstance(incoming,dict) else {}
                    incoming=incoming.get('jobs') if isinstance(incoming,dict) else incoming
                    if not isinstance(incoming,list):raise ValueError('來源格式錯誤')
                    fresh={j['id']:j for j in incoming}
                    if metadata.get('limited'):
                        previous={j['id']:j for j in jobs};previous.update(fresh);fresh=previous
                    jobs=list(fresh.values());fetched=now;error=metadata.get('message') if metadata.get('limited') else None
                    coverage=metadata
                except Exception:
                    error='讀取未完成（連線受限、需要驗證或格式改變）；不是零職缺。'
                with self.db() as conn:
                    conn.execute('INSERT OR REPLACE INTO platform_cache VALUES(?,?,?,?,?,?,?)',(source,query,json.dumps(jobs,ensure_ascii=False),fetched,now,error,json.dumps(coverage,ensure_ascii=False)))
            filtered,reasons=filter_summary(jobs,filters)
            return filtered,status|{'matched':len(filtered),'excluded':reasons,'coverage':coverage}|{'count':len(jobs),'last_success':fetched,'error':error,'state':'error' if error else 'ready'}
