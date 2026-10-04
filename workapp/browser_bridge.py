"""Local, token-authenticated queue for the optional ordinary-browser helper."""
import secrets
import threading
import time
from urllib.parse import urlencode, urlparse

from .platforms import fetch_platform, parse_cards, platform_base


class BrowserBridge:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.last_seen = None
        self.pending = {}

    def authorized(self, token):
        return secrets.compare_digest(token or '', self.token)

    def connected(self):
        return self.last_seen is not None and self.clock() - self.last_seen < 70

    def status(self):
        with self.lock:
            return {'connected': self.connected(), 'pending': len(self.pending)}

    def poll(self):
        with self.lock:
            self.last_seen = self.clock()
            for task in self.pending.values():
                if not task['claimed']:
                    task['claimed'] = True
                    return {k: task[k] for k in ('id', 'source', 'url')}
        return None

    def disconnect(self):
        with self.lock:
            self.last_seen = None
            for task in self.pending.values():
                task['error'] = '瀏覽器助手已停止，已保留先前資料'
                task['event'].set()

    def submit(self, data):
        with self.lock:
            task = self.pending.get(data.get('id'))
            if not task or task['event'].is_set():
                raise ValueError('讀取工作已結束，請重新搜尋')
            html = data.get('html', '')
            if not isinstance(html, str) or len(html) > 2_000_000:
                raise ValueError('職缺內容格式或大小不正確')
            task['html'] = html
            task['error'] = str(data.get('error') or '')[:200]
            task['event'].set()

    def read(self, source, url, timeout=100):
        identifier = secrets.token_urlsafe(18)
        task = {'id': identifier, 'source': source, 'url': url, 'claimed': False,
                'event': threading.Event(), 'html': '', 'error': ''}
        with self.lock:
            self.pending[identifier] = task
        try:
            if not task['event'].wait(timeout):
                raise ValueError('瀏覽器助手逾時；請確認助手已連線，或原站是否要求驗證')
            if task['error']:
                raise ValueError(task['error'])
            parsed = urlparse(url)
            return parse_cards(source, task['html'], f'{parsed.scheme}://{parsed.netloc}')
        finally:
            with self.lock:
                self.pending.pop(identifier, None)

    def fetch(self, source, filters):
        if source not in ('cake', 'indeed') or not self.connected():
            return fetch_platform(source, filters)
        base = platform_base(source, filters)
        found = {}; pages = 0; message = ''; previous = None
        for index in range(2):
            params = {'q': filters['keyword']}
            if source == 'cake':
                params['page'] = index + 1
            else:
                params.update(l=filters['location'], start=index * 10)
            try:
                rows = self.read(source, base + '/jobs?' + urlencode(params))
                signature = tuple(sorted(row['id'] for row in rows))
                if signature == previous:
                    message = '來源重複同一頁，尚未確認結尾'; break
                previous = signature
                found.update({row['id']: row for row in rows}); pages += 1
            except ValueError as exc:
                if not found: raise
                message = str(exc); break
        return {'jobs': list(found.values()), 'coverage': {'pages': pages, 'limited': True,
                'method': 'browser_helper', 'message': message or '一般瀏覽器已讀前兩頁；內文採列表摘要，非全站總數'}}
