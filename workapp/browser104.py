"""User-started, visible 104 browser reader. No challenge solving or API calls."""
import json
import re
import threading
import time
from pathlib import Path
from urllib.parse import urlencode

from .jobs104 import parse_104_html


def page_total(text):
    match = re.search(r'共\s*([\d,]+)\s*筆', text)
    return int(match[1].replace(',', '')) if match else None


class Browser104:
    def __init__(self, db):
        self.db = db
        self.lock = threading.Lock()
        self.cancel = threading.Event()
        self.thread = None
        self.current = {'state': 'idle', 'keyword': '', 'pages': 0, 'count': 0, 'total': None}
        with db() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS browser104(keyword TEXT PRIMARY KEY,payload TEXT NOT NULL,updated_at REAL NOT NULL)')

    def saved(self, keyword):
        with self.db() as conn:
            row = conn.execute('SELECT payload,updated_at FROM browser104 WHERE keyword=?', (keyword.casefold(),)).fetchone()
        return (json.loads(row['payload']), row['updated_at']) if row else (None, None)

    def status(self):
        with self.lock:
            return dict(self.current)

    def stop(self):
        self.cancel.set()
        return self.status()

    def start(self, keyword, resume=False):
        keyword = keyword.strip()
        if not keyword or len(keyword) > 200 or re.search('[,，]', keyword):
            raise ValueError('請輸入一個 104 搜尋關鍵字。')
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise ValueError('104 正在讀取，請先停止目前工作。')
            self.cancel.clear()
            self.current = {'state': 'starting', 'keyword': keyword, 'pages': 0, 'count': 0, 'total': None,
                            'message': '正在開啟 104 瀏覽器；若出現驗證，請在該視窗手動完成。'}
            self.thread = threading.Thread(target=self.run, args=(keyword, resume), daemon=True)
            self.thread.start()
            return dict(self.current)

    def update(self, **values):
        with self.lock:
            self.current.update(values)

    def persist(self, keyword, jobs, next_page, previous_jobs=None):
        progress = self.status()
        available = jobs if progress['state']=='complete' else {**(previous_jobs or {}), **jobs}
        payload = {'jobs': list(available.values()), 'run_jobs': list(jobs.values()), 'progress': progress, 'next_page': next_page,
                   'data_at': max((j.get('read_at',0) for j in available.values()), default=time.time())}
        with self.db() as conn:
            conn.execute('INSERT OR REPLACE INTO browser104 VALUES(?,?,?)',
                         (keyword.casefold(), json.dumps(payload, ensure_ascii=False), time.time()))

    def run(self, keyword, resume):
        jobs = {}
        page = 1
        saved = None
        previous_jobs = {}
        try:
            from playwright.sync_api import sync_playwright
            saved, _ = self.saved(keyword)
            previous_jobs = {j['id']: j for j in saved['jobs']} if saved else {}
            if resume and saved and saved['progress']['state'] != 'complete':
                jobs = {j['id']: j for j in saved.get('run_jobs',saved['jobs'])}
                page = saved['next_page']
                self.update(pages=page-1, count=len(jobs), total=saved['progress'].get('total'))
            with sync_playwright() as p:
                channel = 'msedge' if Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe').is_file() else None
                browser = p.chromium.launch(headless=False, channel=channel)
                try:
                    context = browser.new_context(locale='zh-TW', viewport={'width': 1280, 'height': 900})
                    tab = context.new_page()
                    tab.goto('https://www.104.com.tw/jobs/search/?' + urlencode({'keyword': keyword, 'page': page}),
                             wait_until='domcontentloaded', timeout=45000)
                    previous = None
                    started = time.monotonic()
                    while not self.cancel.is_set():
                        # Ordinary visible browser: wait for the person if a challenge is shown.
                        deadline = time.monotonic() + 300
                        content_deadline = time.monotonic() + 45
                        rows = None
                        while time.monotonic() < deadline and not self.cancel.is_set():
                            text = tab.locator('body').inner_text(timeout=5000)
                            if 'Just a moment' in tab.title() or 'Verify you are human' in text or '確認您是人類' in text:
                                self.update(state='waiting_user', message='請在開啟的 104 視窗完成網站驗證；完成後會自動繼續。')
                                content_deadline = time.monotonic() + 45
                            else:
                                try:
                                    candidate = parse_104_html(tab.content())
                                    fingerprint = tuple(j['id'] for j in candidate)
                                    if fingerprint != previous:
                                        rows = candidate
                                        previous = fingerprint
                                        break
                                except ValueError:
                                    pass
                                if time.monotonic() >= content_deadline:
                                    raise ValueError(f'第 {page} 頁沒有載入職缺卡片，無法確認搜尋結果；已保留資料。')
                                self.update(state='loading', message=f'正在等待第 {page} 頁內容；可在 104 視窗確認頁面狀態。')
                            tab.wait_for_timeout(1000)
                        if self.cancel.is_set():
                            break
                        if rows is None:
                            raise ValueError(f'第 {page} 頁等待逾時，已保留先前結果；可按接續讀取。')
                        for job in rows:
                            job['read_at'] = time.time()
                            jobs[job['id']] = job
                        # Counter and paging controls may render after the cards.
                        tab.wait_for_timeout(1000)
                        text = tab.locator('body').inner_text(timeout=5000)
                        total = page_total(text)
                        if total == 0 and jobs:
                            total = None
                        self.update(state='reading', pages=page, count=len(jobs), total=total,
                                    message=f'已讀第 {page} 頁，取得 {len(jobs)} 筆不重複職缺。')
                        page += 1
                        self.persist(keyword, jobs, page, previous_jobs)
                        # Desktop uses links, including a disabled next arrow on the final page.
                        next_button = tab.locator(f'li.paging__item:not(.disable) > a.paging__link[href="?page={page}"]')
                        has_next = next_button.count() > 0 and next_button.first.is_visible() and next_button.first.is_enabled()
                        if not has_next:
                            complete = total is not None and len(jobs) >= total
                            self.update(state='complete' if complete else 'partial',
                                        message='已讀到網站最後一頁。' if complete else '網站沒有可用的下一頁，但筆數尚未核對完整；保留結果，不宣稱已讀完。')
                            break
                        if page > 500 or time.monotonic() - started > 1800:
                            self.update(state='partial', message='本輪到達 500 頁／30 分鐘上限；可接續讀取。')
                            break
                        tab.wait_for_timeout(3000)
                        if not self.cancel.is_set():
                            next_button.first.click(timeout=15000)
                    if self.cancel.is_set():
                        self.update(state='paused', message='已停止並保存進度，可接續讀取。')
                finally:
                    browser.close()
        except Exception as exc:
            self.update(state='partial' if jobs else 'error', message=str(exc)[:220])
        finally:
            if previous_jobs and self.status()['state']!='complete':
                self.update(message=self.status().get('message', '') + ' 未更新部分保留前次職缺快照。')
            self.persist(keyword, jobs, page, previous_jobs)
