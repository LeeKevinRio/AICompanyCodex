"""104 query-scoped search, adapted from the user's WorkManager architecture."""
import json
import re
import threading
import time
from datetime import datetime
from urllib.parse import urlencode, urlparse
from .domain import matches, plain_text, keyword_matches


def fetch_104(keyword):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ValueError('104 瀏覽器元件未安裝，請依 README 啟動虛擬環境。') from None
    out = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for page in (1, 2):
                payload = None
                last_error = None
                for attempt in range(3):
                    context = browser.new_context(locale='zh-TW', viewport={'width':1366,'height':900})
                    try:
                        tab = context.new_page()
                        response = tab.goto('https://www.104.com.tw/jobs/search/?' + urlencode({'keyword':keyword}), wait_until='domcontentloaded', timeout=45000)
                        if response is None: raise ValueError('104 搜尋頁沒有回應')
                        # Match WorkManager: an initial HTTP status is not the final page state.
                        try:
                            tab.wait_for_function("() => document.title && !document.title.includes('Just a moment')", timeout=30000)
                        except Exception:
                            pass
                        tab.wait_for_timeout(1500)
                        api = '/jobs/search/api/jobs?' + urlencode({'keyword':keyword,'order':15,'mode':'s','page':page,'jobsource':'2018indexpoc'})
                        for retry in range(5):
                            result = tab.evaluate("""async url => { const r = await fetch(url, {credentials:'include',headers:{Accept:'application/json'},signal:AbortSignal.timeout(30000)}); return {status:r.status,text:await r.text()}; }""", api)
                            if result['status'] == 200:
                                payload = json.loads(result['text'])
                                break
                            last_error = ValueError(f"104 第 {page} 頁 API HTTP {result['status']}（搜尋頁 HTTP {response.status}）；等待後仍未取得資料")
                            tab.wait_for_timeout(2000)
                        if payload is not None: break
                    except Exception as exc:
                        last_error = exc
                    finally:
                        context.close()
                    if attempt < 2: time.sleep(2 ** attempt)
                if payload is None:
                    raise ValueError(str(last_error)[:180] if isinstance(last_error,ValueError) else '104 瀏覽器等待／讀取失敗')
                rows = payload.get('data') if isinstance(payload,dict) else None
                if isinstance(rows, dict): rows = rows.get('list')
                if not isinstance(rows, list): raise ValueError('104 回傳格式不完整。')
                out.extend(rows)
                if not rows: break
            return out
        finally:
            browser.close()


def normalize_104(row):
    url = (row.get('link') or {}).get('job') or ''
    if url.startswith('//'): url = 'https:' + url
    parsed = urlparse(url)
    if parsed.scheme not in ('https','http') or parsed.hostname not in ('www.104.com.tw','104.com.tw') or not re.fullmatch(r'/job/[a-zA-Z0-9]+/?',parsed.path):
        raise ValueError('104 職缺連結格式不完整')
    tags = row.get('tags') or {}
    tags = [v.get('desc','') for v in tags.values() if isinstance(v,dict)] if isinstance(tags,dict) else [v for v in tags if isinstance(v,str)]
    title = plain_text(row.get('jobName',''))
    description = plain_text(row.get('description',''))
    hint = ' '.join([title,description,*tags]).lower()
    remote = 'unknown'
    if re.search(r'部分遠端|混合辦公|hybrid',hint): remote = 'hybrid'
    elif re.search(r'不(?:提供|接受|開放|可)?遠端|無法遠端|no remote|on.site only',hint): remote = 'onsite'
    elif re.search(r'全遠端|完全遠端|fully remote|100% remote',hint): remote = 'remote'
    salary = plain_text(row.get('salaryDesc') or '薪資未公開')
    period = 'month' if '月薪' in salary else 'year' if '年薪' in salary else None
    def amount(key):
        try:
            value = float(row.get(key) or 0)
            return value if 0 < value < 100000000 else None
        except (ValueError,TypeError): return None
    location = plain_text(row.get('jobAddrNoDesc',''))
    taiwan = bool(re.search(r'台[北中南東灣]|臺[北中南東灣]|新北|桃園|新竹|苗栗|彰化|南投|雲林|嘉義|高雄|屏東|宜蘭|花蓮|基隆|澎湖|金門|連江',location))
    # Currency must not silently become TWD for overseas postings.
    currency = 'USD' if re.search(r'USD|US\$|美元',salary,re.I) else 'TWD' if re.search(r'TWD|NT\$|新台幣',salary,re.I) else None
    foreign = bool(re.search(r'人民幣|日圓|日元|港幣|港元|歐元|英鎊|RMB|CNY|JPY|HKD|EUR|GBP',salary,re.I))
    if currency is None and taiwan and not foreign: currency = 'TWD'
    published = str(row.get('appearDate') or '')
    for fmt in ('%Y%m%d','%Y/%m/%d','%Y-%m-%d'):
        try:
            published = datetime.strptime(published,fmt).date().isoformat()
            break
        except ValueError: pass
    else: published = ''
    return {'id':'104:'+parsed.path.strip('/').split('/')[-1],'source':'104','source_name':'104 人力銀行','title':title,'company':plain_text(row.get('custName','')),'url':'https://www.104.com.tw'+parsed.path,'description':description,'tags':', '.join(tags),'location':location,'taiwan':taiwan,'local_taiwan':taiwan,'remote':remote,'salary':salary,'salary_min':amount('salaryLow') if period and currency else None,'salary_max':amount('salaryHigh') if period and currency else None,'currency':currency if period else None,'period':period,'published':published}


class Search104:
    def __init__(self, db, fetcher=fetch_104, clock=time.time):
        self.db,self.fetcher,self.clock = db,fetcher,clock
        self.lock=threading.Lock()
        with db() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS search104_cache(keyword TEXT PRIMARY KEY,payload TEXT,fetched_at REAL,attempted_at REAL,error TEXT)')

    def search(self, filters):
        keyword=filters['keyword'].strip()
        base={'results':[],'state':'ready','message':'','fetched_at':None,'cached':False,'stale':False}
        if not keyword: return base | {'state':'needs_keyword','message':'請輸入職稱、技能或公司，再搜尋 104。'}
        if ',' in keyword or '，' in keyword:
            return base | {'state':'needs_keyword','message':'104 每次搜尋一個關鍵字，請分別搜尋。'}
        with self.lock:
            now=self.clock()
            with self.db() as conn:
                row=conn.execute('SELECT * FROM search104_cache WHERE keyword=?',(keyword.casefold(),)).fetchone()
            jobs=json.loads(row['payload']) if row and row['payload'] else []
            fetched=row['fetched_at'] if row else None
            error=row['error'] if row else None
            due = not row or now-row['attempted_at'] >= (300 if error else 1800)
            if due:
                try:
                    jobs=list({j['id']:j for j in (normalize_104(r) for r in self.fetcher(keyword))}.values())
                    fetched,error=now,None
                except Exception as exc:
                    error=(str(exc)[:180]+'；' if isinstance(exc,ValueError) else '')+'104 未能完成讀取（可能需要網站驗證或連線失敗）。保留前次資料；不代表沒有職缺。'
                with self.db() as conn:
                    conn.execute('INSERT OR REPLACE INTO search104_cache VALUES(?,?,?,?,?)',(keyword.casefold(),json.dumps(jobs,ensure_ascii=False),fetched,now,error))
            found=[j for j in jobs if matches(j,filters)]
            found.sort(key=lambda j:keyword_matches(j['title'].casefold(),keyword.casefold()),reverse=True)
            return base | {'results':found,'fetched_at':fetched,'cached':not due,'stale':bool(error and fetched),'state':'error' if error else 'ready','message':error or '', 'fetched_count':len(jobs)}
