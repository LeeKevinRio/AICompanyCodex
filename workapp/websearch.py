"""Query-scoped Google results. Never treated as a complete job inventory."""
import json
import os
import re
import threading
import time
import urllib.request
from urllib.parse import urlencode, urlparse
from .domain import keyword_matches, plain_text


def build_query(filters):
    words = [w.strip().replace('"', ' ').replace('\\', ' ') for w in re.split('[,，]', filters['keyword']) if w.strip()]
    keywords = '(' + ' OR '.join('"' + w + '"' for w in words) + ')'
    mode = {'remote': '("完全遠端" OR "全遠端" OR "fully remote")',
            'hybrid': '("部分遠端" OR "混合辦公" OR hybrid)',
            'onsite': '("現場辦公" OR "on-site")'}.get(filters['remote'], '')
    location = '"' + filters['location'].replace('"', ' ') + '"' if filters['location'] else ''
    return ' '.join(x for x in ['(site:104.com.tw/job/ OR site:1111.com.tw/job/)', keywords, location, mode] if x)


def fetch_google(query, key):
    url = 'https://serpapi.com/search.json?' + urlencode({
        'engine': 'google', 'q': query, 'api_key': key, 'gl': 'tw', 'hl': 'zh-tw', 'start': 0})
    try:
        with urllib.request.urlopen(url, timeout=25) as response:
            payload = json.load(response)
    except Exception:
        # URLs and upstream errors may contain the API key. Never surface them.
        raise ValueError('搜尋服務連線失敗，請檢查金鑰、額度或網路。') from None
    if not isinstance(payload, dict) or payload.get('error') or payload.get('search_metadata', {}).get('status') != 'Success':
        raise ValueError('搜尋服務未成功完成，請檢查金鑰與可用額度。')
    results = payload.get('organic_results')
    if results is None and payload.get('search_information', {}).get('organic_results_state') == 'Fully empty':
        return []
    if not isinstance(results, list):
        raise ValueError('搜尋服務回傳格式不完整，保留前次結果。')
    return results


def normalize_results(items, filters):
    results, seen = [], set()
    keywords = [w.strip().casefold() for w in re.split('[,，]', filters['keyword']) if w.strip()]
    for item in items:
        if not isinstance(item, dict):
            continue
        url = urlparse(str(item.get('link', '')))
        host = (url.hostname or '').lower()
        source = '104' if host in ('104.com.tw', 'www.104.com.tw') else '1111' if host in ('1111.com.tw', 'www.1111.com.tw') else None
        if url.scheme not in ('http', 'https') or not source or url.username or url.password:
            continue
        match = re.fullmatch(r'/job/([a-zA-Z0-9]+)/?', url.path)
        if not match or (source == '1111' and not match[1].isdigit()):
            continue
        canonical = f'https://www.{source}.com.tw/job/{match[1]}'
        title, snippet = plain_text(str(item.get('title', ''))), plain_text(str(item.get('snippet', '')))
        haystack = (title + ' ' + snippet).casefold()
        if not title or canonical in seen or (keywords and not any(keyword_matches(haystack, w) for w in keywords)):
            continue
        seen.add(canonical)
        results.append({'title': title, 'description': snippet, 'source': source, 'url': canonical})
    return results


class WebSearch:
    def __init__(self, db, fetcher=fetch_google, clock=time.time):
        self.db, self.fetcher, self.clock = db, fetcher, clock
        self.lock = threading.Lock()
        with db() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS web_search_cache(query TEXT PRIMARY KEY, payload TEXT, fetched_at REAL)')
            conn.execute('CREATE TABLE IF NOT EXISTS web_search_requests(requested_at REAL)')

    def search(self, filters):
        query = build_query(filters)
        base = {'results': [], 'query': query, 'fetched_at': None, 'cached': False, 'stale': False}
        if not filters['keyword'].strip(' ,，'):
            return base | {'state': 'needs_keyword', 'message': '請先輸入職稱、技能或公司。'}
        with self.lock:
            now = self.clock()
            with self.db() as conn:
                old = conn.execute('SELECT * FROM web_search_cache WHERE query=?', (query,)).fetchone()
            if old:
                base.update(results=json.loads(old['payload']), fetched_at=old['fetched_at'], cached=True)
                if now - old['fetched_at'] < 21600:
                    return base | {'state': 'ready'}
                base['stale'] = True
            key = os.environ.get('WORKAPP_SERPAPI_KEY', '').strip()
            if not key:
                return base | {'state': 'not_configured', 'message': '尚未設定 Google 搜尋服務金鑰；不是沒有職缺。請依下方接入說明設定 SerpApi。'}
            with self.db() as conn:
                conn.execute('DELETE FROM web_search_requests WHERE requested_at<?', (now - 3600,))
                count = conn.execute('SELECT count(*) FROM web_search_requests').fetchone()[0]
                if count >= 10:
                    return base | {'state': 'limited', 'message': '已達每小時 10 次搜尋上限，請稍後再試。'}
                conn.execute('INSERT INTO web_search_requests VALUES(?)', (now,))
            try:
                results = normalize_results(self.fetcher(query, key), filters)
            except Exception:
                return base | {'state': 'error', 'message': '搜尋未完成，請檢查服務金鑰、額度或網路；已有結果會保留。'}
            with self.db() as conn:
                conn.execute('INSERT OR REPLACE INTO web_search_cache VALUES(?,?,?)', (query, json.dumps(results, ensure_ascii=False), now))
            return base | {'state': 'ready', 'results': results, 'fetched_at': now, 'cached': False, 'stale': False}
