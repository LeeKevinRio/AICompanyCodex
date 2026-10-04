"""Bounded, query-scoped public job searches; no login or challenge bypass."""
import hashlib
import json
import re
import threading
import time
import urllib.request
import urllib.error
from urllib.parse import urlencode, urljoin, urlparse, parse_qs
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
    # Search highlights can split opport<b>unity</b>; do not invent word boundaries.
    for highlight in soup.select('mark, b, strong, em'):
        highlight.unwrap()
    soup.smooth()
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
        for card in soup.select('div.job_seen_beacon, a.tapItem'):
            card=card.find_parent(class_='cardOutline') or card
            anchor=card if card.name=='a' and card.get('href') else card.select_one('a.jcs-JobTitle, h3.jobTitle a, h2.jobTitle a, a.tapItem')
            if not anchor: continue
            title=text(card,'h3.jobTitle span, h2.jobTitle span, h2 a span') or anchor.get_text(' ',strip=True)
            out.append(job(source,title,text(card,"[data-testid='company-name'], .companyName"),text(card,"[data-testid='text-location'], .companyLocation"),urljoin(base,anchor['href']),description=text(card,".job-snippet, [data-testid='belowJobSnippet']"),salary=text(card,"[data-testid*='salary'], [class*='salary-snippet']")))
    else:
        for anchor in soup.select("a[class*='jobTitle'][href*='/companies/'][href*='/jobs/']"):
            card=anchor;root=None
            for _ in range(6):
                card=card.parent
                if card is None: break
                if any('JobSearchItem' in c and 'content' in c for c in card.get('class',[])):
                    root=card;break
            card=root or anchor.find_parent('article') or anchor.find_parent('div') or anchor.parent
            company=text(card,"[class*='companyName']")
            if not company:
                parts=urlparse(anchor['href']).path.split('/')
                company=parts[parts.index('companies')+1].replace('-',' ').title()
            location=' / '.join(dict.fromkeys(a.get_text(' ',strip=True) for a in card.select("a[href*='/in-']"))) or text(card,"[class*='features']")
            description=' '.join(filter(None,[text(card,"[class*='description']"),text(card,"[class*='tags']")]))
            out.append(job(source,anchor.get_text(' ',strip=True),company,location,urljoin(base,anchor['href']).split('?')[0],description=description,salary=text(card,"[class*='salary']")))
    if not out:
        # Empty shell / CAPTCHA / changed selectors must not become a false zero.
        raise ValueError('沒有取得可辨識的職缺卡片，可能無結果、頁面改版或需要驗證')
    if source=='indeed':
        for row in out:
            key=parse_qs(urlparse(row['url']).query).get('jk',[''])[0]
            if re.fullmatch(r'[a-zA-Z0-9_-]+',key):
                row['id']='indeed:'+key
                row['url']=base+'/viewjob?'+urlencode({'jk':key})
    return list({j['id']:j for j in out}.values())


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
    prior_coverage=filters.get('_coverage',{}) if filters.get('_resume') and filters.get('_coverage',{}).get('cursors') else {}
    cursors={(q['keyword'],q['location']):q for q in prior_coverage.get('cursors',[])}
    for q in queries:
        old=cursors.get((q['keyword'],q['location']))
        if old:
            q.update(offset=old['offset'],done=old['done'],last=tuple(old.get('last',[])))
    previous={j['id']:j for j in filters.get('_previous_jobs',[])}
    found=dict(previous) if filters.get('_resume') else {};pages=0;stop='';started=clock();attempts=0
    detail_first=bool(prior_coverage.get('unverified_details'))
    if detail_first and not all(q['done'] for q in queries):
        stop='先補讀已取得職缺的內文，保留後續分頁進度'
    while queries and not detail_first and not all(q['done'] for q in queries):
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
                document=BeautifulSoup(html,'html.parser')
                # Guest endpoint ends with a doctype/comment-only document, not always ''.
                if not document.find() and not document.get_text(strip=True):
                    q['done']=True;continue
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
                if signature==q.get('last'):
                    q['offset']-=len(rows)
                    stop='來源重複回傳同一頁，未確認已到結尾；已保留分頁進度'
                    break
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
    return {'jobs':list(found.values()),'coverage':{'pages':pages+prior_coverage.get('pages',0),'round_pages':pages,'cursors':queries,'detail_pages':detail_pages,'unverified_details':unresolved,'queries':len(queries),'finished_queries':sum(q['done'] for q in queries),'limited':bool(stop),'message':stop or '目前查詢已讀到結尾；仍非全網職缺總數'}}


def filter_summary(jobs, filters):
    remaining=list(jobs);reasons={}
    neutral=dict(filters,region='global',remote='any',location='',keyword='',salary_min=0)
    for key,label in [('keyword','關鍵字'),('region','應徵地區'),('location','地點'),('remote','工作模式'),('salary_min','薪資')]:
        trial=neutral|{key:filters[key]}
        kept=[j for j in remaining if matches(j,trial)]
        if len(remaining)!=len(kept): reasons[label]=len(remaining)-len(kept)
        remaining=kept
    return remaining,reasons


def wait_for_job_content(tab, response, selector, timeout=30000):
    """Allow an interstitial to finish naturally; never click/solve verification."""
    if response is None:
        raise ValueError('搜尋頁沒有回應')
    challenge = response.headers.get('cf-mitigated') == 'challenge' or bool(re.search(r'just a moment|captcha|security check|請稍候|安全驗證', tab.title(), re.I))
    if response.status >= 400 and not challenge:
        raise ValueError(f'搜尋頁 HTTP {response.status}')
    try:
        tab.wait_for_selector(selector, timeout=timeout)
    except Exception:
        title = tab.title()
        if challenge or re.search(r'just a moment|captcha|verify|security check|請稍候|安全驗證', title, re.I):
            raise ValueError('網站驗證尚未完成；已等待頁面自行載入，未取得職缺') from None
        raise ValueError('等待職缺內容逾時，可能頁面改版或沒有結果') from None


def platform_base(source, filters):
    if source == 'cake': return 'https://www.cake.me'
    return 'https://tw.indeed.com' if filters['region'] == 'taiwan' else 'https://www.indeed.com'


def fetch_browser_platform(source, filters):
    """Port WorkManager's rendered lists and Cake detail pass, preserving partial data."""
    from playwright.sync_api import sync_playwright
    keyword=filters['keyword']
    location=filters['location']
    base=platform_base(source, filters)
    selector="a[href*='/companies/'][href*='/jobs/']" if source=='cake' else 'div.job_seen_beacon, a.tapItem'
    found={};pages=0;details=0;warning='';started=time.monotonic()
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            context=browser.new_context(locale='en-US',viewport={'width':1366,'height':900})
            tab=context.new_page()
            for index in range(2):
                if index:time.sleep(1.5)
                url=base+'/jobs?'+urlencode({'q':keyword,'page':index+1} if source=='cake' else {'q':keyword,'l':location,'start':index*10})
                try:
                    response=tab.goto(url,wait_until='domcontentloaded',timeout=60000 if source=='cake' else 30000)
                    wait_for_job_content(tab,response,selector)
                    if source=='cake':tab.wait_for_timeout(1500)
                    rows=parse_cards(source,tab.content(),base)
                    for row in rows:found[row['id']]=row
                    pages+=1
                except Exception as exc:
                    warning=str(exc)[:160] if isinstance(exc,ValueError) else f'第 {index+1} 頁等待逾時或連線失敗'
                    if not found:raise ValueError(warning) from None
                    break
            # The original Cake second pass fills missing descriptions/salaries.
            if source=='cake' and not warning:
                for row in list(found.values())[:15]:
                    if time.monotonic()-started>120:
                        warning='詳細內容到達本輪時間上限';break
                    time.sleep(1)
                    try:
                        response=tab.goto(row['url'],wait_until='domcontentloaded',timeout=30000)
                        if response is None or response.status>=400:
                            warning='詳細頁讀取受限，已保留列表';break
                        if re.search(r'just a moment|captcha|verify',tab.title(),re.I):
                            warning='詳細頁需要驗證，已保留列表';break
                        tab.wait_for_selector("[class*='JobDescription']",timeout=15000)
                        soup=BeautifulSoup(tab.content(),'html.parser')
                        desc=soup.select_one("[class*='JobDescription_content'], [class*='JobDescription']")
                        if desc:row['description']=desc.get_text(' ',strip=True)[:8000];details+=1
                        if row['salary']=='薪資未公開':
                            salary=next((n.get_text(' ',strip=True) for n in soup.select("[class*='salary'], [class*='Salary']") if 0<len(n.get_text(' ',strip=True))<200),'')
                            if salary:row.update(salary=salary,**salary_fields(salary))
                    except Exception:
                        warning='部分詳細內容未能讀取，已保留列表';break
        finally:browser.close()
    return {'jobs':list(found.values()),'coverage':{'pages':pages,'detail_pages':details,'limited':True,
            'message':warning or '已讀前兩頁；沿用 WorkManager 的讀取範圍，非全站總數'}}


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
    return fetch_browser_platform(source,filters)


class PlatformSearch:
    def __init__(self,db,fetcher=fetch_platform,clock=time.time,cache_namespace=None):
        self.db,self.fetcher,self.clock=db,fetcher,clock
        self.cache_namespace=cache_namespace or (lambda source:'')
        self.locks={k:threading.Lock() for k in PLATFORMS}
        with db() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS platform_cache(source TEXT, query TEXT, payload TEXT, fetched_at REAL, attempted_at REAL, error TEXT, PRIMARY KEY(source,query))')
            if 'coverage' not in [r[1] for r in conn.execute('PRAGMA table_info(platform_cache)')]:
                conn.execute("ALTER TABLE platform_cache ADD COLUMN coverage TEXT NOT NULL DEFAULT '{}'")

    def search(self,source,filters, resume=False):
        query=json.dumps({k:filters[k] for k in ('keyword','region','location')},sort_keys=True)
        if source=='remoteok': query='feed'
        elif source=='linkedin': query='v3:'+query
        query=self.cache_namespace(source)+query
        status={'id':source,'name':PLATFORMS[source],'count':0,'last_success':None,'error':None,'refresh_minutes':360 if source=='remoteok' else 30,'note':('台灣／全球分開查詢、別名與分頁；非全站總數' if source=='linkedin' else '公開搜尋前兩頁；Cake最多補讀15筆內文；非全站職缺') if source!='remoteok' else '公開職缺 feed；地區未知不推定台灣可應徵'}
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
                    incoming=self.fetcher(source,filters|{'_previous_jobs':jobs,'_coverage':coverage,'_resume':resume or bool(coverage.get('limited') and coverage.get('cursors'))})
                    metadata=incoming.get('coverage',{}) if isinstance(incoming,dict) else {}
                    incoming=incoming.get('jobs') if isinstance(incoming,dict) else incoming
                    if not isinstance(incoming,list):raise ValueError('來源格式錯誤')
                    fresh={j['id']:j for j in incoming}
                    if metadata.get('limited'):
                        previous={j['id']:j for j in jobs};previous.update(fresh);fresh=previous
                    jobs=list(fresh.values());fetched=now;error=metadata.get('message') if metadata.get('limited') else None
                    coverage=metadata
                except Exception as exc:
                    error=(str(exc)[:160]+'；' if isinstance(exc,ValueError) else '')+'讀取未完成（連線受限、需要驗證或格式改變）；不是零職缺。'
                with self.db() as conn:
                    conn.execute('INSERT OR REPLACE INTO platform_cache VALUES(?,?,?,?,?,?,?)',(source,query,json.dumps(jobs,ensure_ascii=False),fetched,now,error,json.dumps(coverage,ensure_ascii=False)))
            filtered,reasons=filter_summary(jobs,filters)
            return filtered,status|{'matched':len(filtered),'excluded':reasons,'coverage':coverage}|{'count':len(jobs),'last_success':fetched,'error':error,'state':'error' if error else 'ready'}
