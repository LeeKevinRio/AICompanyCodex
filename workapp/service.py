import json
import re
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from .domain import matches, validate_filters
from .providers import SOURCES, fetch_source
from .websearch import WebSearch
from .jobs104 import Search104
from .platforms import PlatformSearch, filter_summary
from .domain import keyword_matches
from .browser_bridge import BrowserBridge


class Service:
    def __init__(self, database="data/workapp.sqlite3", fetcher=fetch_source, clock=time.time):
        Path(database).parent.mkdir(parents=True, exist_ok=True)
        self.database, self.fetcher, self.clock = str(database), fetcher, clock
        self.refresh_lock, self.scan_lock = threading.Lock(), threading.Lock()
        self.stop = threading.Event()
        with self.db() as conn:
            conn.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, source TEXT NOT NULL, payload TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, last_success REAL, last_attempt REAL, error TEXT, count INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS rules(id INTEGER PRIMARY KEY, name TEXT NOT NULL, filters TEXT NOT NULL, hours INTEGER NOT NULL, paused INTEGER DEFAULT 0, next_run REAL NOT NULL, last_run REAL);
                CREATE TABLE IF NOT EXISTS discoveries(rule_id INTEGER NOT NULL REFERENCES rules(id) ON DELETE CASCADE, job_id TEXT NOT NULL, discovered_at REAL NOT NULL, PRIMARY KEY(rule_id, job_id));
                CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, rule_id INTEGER NOT NULL REFERENCES rules(id) ON DELETE CASCADE, ran_at REAL NOT NULL, matches INTEGER NOT NULL, new_count INTEGER NOT NULL, warnings TEXT NOT NULL);
            ''')
            for key in SOURCES:
                conn.execute("INSERT OR IGNORE INTO sources(id) VALUES (?)", (key,))
        self.web_search = WebSearch(self.db)
        self.search104 = Search104(self.db)
        self.browser_bridge = BrowserBridge()
        self.platforms = PlatformSearch(self.db, fetcher=self.browser_bridge.fetch,
            cache_namespace=lambda source: 'browser-helper:' if source in ('cake', 'indeed') and self.browser_bridge.connected() else '')

    @contextmanager
    def db(self):
        conn = sqlite3.connect(self.database, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def source_status(self):
        with self.db() as conn:
            rows = conn.execute("SELECT * FROM sources").fetchall()
        return [dict(row) | {"name": SOURCES[row["id"]]["name"], "refresh_minutes": SOURCES[row["id"]]["ttl"] // 60} for row in rows]

    def refresh(self, selected=None):
        # Cache lives in SQLite and survives restarts; Remotive at most 4/day.
        with self.refresh_lock:
            now = self.clock()
            due = [s for s in self.source_status() if (selected is None or s['id'] in selected) and (s["last_attempt"] is None or now - s["last_attempt"] >= (SOURCES[s["id"]]["ttl"] if s["id"] == "remotive" or (s["last_success"] is not None and not s["error"]) else 300))]
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = {s["id"]: pool.submit(self.fetcher, s["id"]) for s in due}
                for key, future in futures.items():
                    try:
                        jobs = future.result()
                        if not isinstance(jobs, list) or any(j["source"] != key for j in jobs):
                            raise ValueError("職缺資料格式不正確")
                        with self.db() as conn:
                            conn.execute("UPDATE jobs SET active=0 WHERE source=?", (key,))
                            conn.executemany("INSERT INTO jobs(id,source,payload,active) VALUES(?,?,?,1) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, active=1", [(j["id"], key, json.dumps(j, ensure_ascii=False)) for j in jobs])
                            conn.execute("UPDATE sources SET last_success=?,last_attempt=?,error=NULL,count=? WHERE id=?", (now, now, len(jobs), key))
                    except Exception as exc:
                        with self.db() as conn:
                            conn.execute("UPDATE sources SET last_attempt=?,error=? WHERE id=?", (now, str(exc)[:300], key))
        return self.source_status()

    def jobs(self, filters):
        with self.db() as conn:
            rows = conn.execute("SELECT payload FROM jobs WHERE active=1").fetchall()
        jobs = [json.loads(r["payload"]) for r in rows]
        result = [job for job in jobs if matches(job, filters)]
        return sorted(result, key=lambda j: (j.get("local_taiwan", j["taiwan"] and not re.search(r"worldwide|anywhere|global", j["location"], re.I)), j["taiwan"], j["published"]), reverse=True)

    def search_all(self, filters, resume=False):
        selected = filters.get('sources', ['appier','canonical','remotive'])
        statuses = [s for s in self.refresh(selected) if s['id'] in selected]
        jobs = [j for j in self.jobs(filters) if j['source'] in selected and j['source'] in SOURCES]
        with self.db() as conn:
            raw=[json.loads(r['payload']) for r in conn.execute('SELECT payload FROM jobs WHERE active=1')]
        for status in statuses:
            matched,excluded=filter_summary([j for j in raw if j['source']==status['id']],filters)
            status.update(matched=len(matched),excluded=excluded)

        def query(source):
            if source != '104':
                found, status = self.platforms.search(source,filters,resume=resume)
                if source in ('cake','indeed'):
                    status['helper_connected'] = self.browser_bridge.connected()
                    if status.get('error') and not status['helper_connected']:
                        status['action'] = '瀏覽器助手未連線；請展開上方助手設定，安裝並配對後再搜尋。'
                    if source == 'indeed' and filters['region'] == 'global':
                        status['note'] += '；目前 Indeed 全球模式僅接美國站，尚未涵蓋各國站。'
                return found, status
            data = self.search104.search(filters)
            progress=data.get('browser_progress')
            note=(f"瀏覽器已讀 {progress['pages']} 頁，{progress['count']} 筆／網站 {progress.get('total') if progress.get('total') is not None else '未知'} 筆；狀態 {progress['state']}" if progress else 'API 前兩頁；可開啟瀏覽器逐頁完整讀取')
            return data['results'], {'id':'104','name':'104 人力銀行','matched':len(data['results']),'count':data.get('fetched_count',0),'last_success':data['fetched_at'],'error':data['message'] if data['state']!='ready' else None,'refresh_minutes':30,'note':note+f"；另有 {data.get('imported_count',0)} 筆手動匯入快照（不自動更新）",'state':data['state']}
        extra = [s for s in selected if s not in SOURCES]
        with ThreadPoolExecutor(max_workers=2) as pool:
            for found,status in pool.map(query,extra):
                jobs.extend(found);statuses.append(status)
        terms=[v.strip().casefold() for v in re.split('[,，]',filters['keyword']) if v.strip()]
        jobs=list({j['id']:j for j in jobs}.values())
        jobs.sort(key=lambda j:(any(keyword_matches(j['title'].casefold(),t) for t in terms),j['taiwan'] if filters['region']=='taiwan' else False,j['published']),reverse=True)
        return jobs,statuses

    def rules(self):
        with self.db() as conn:
            rows = conn.execute("SELECT r.*, (SELECT count(*) FROM discoveries d WHERE d.rule_id=r.id) AS discovered_count FROM rules r ORDER BY id DESC").fetchall()
            result = []
            for row in rows:
                rule = dict(row)
                rule["filters"] = json.loads(rule["filters"])
                latest = conn.execute("SELECT * FROM runs WHERE rule_id=? ORDER BY id DESC LIMIT 1", (rule["id"],)).fetchone()
                rule["latest"] = dict(latest) if latest else None
                if rule["latest"]:
                    rule["latest"]["warnings"] = json.loads(rule["latest"]["warnings"])
                result.append(rule)
        return result

    def add_rule(self, data):
        filters = validate_filters(data.get("filters", {}))
        name = str(data.get("name", "")).strip()
        hours = data.get("hours", 6)
        if not name or len(name) > 80 or hours not in (6, 12, 24):
            raise ValueError("請填寫名稱（最多 80 字），掃描頻率為 6、12 或 24 小時")
        with self.db() as conn:
            if conn.execute("SELECT count(*) FROM rules").fetchone()[0] >= 50:
                raise ValueError("最多可建立 50 組掃描條件")
            rule_id = conn.execute("INSERT INTO rules(name,filters,hours,next_run) VALUES(?,?,?,?)", (name, json.dumps(filters), hours, self.clock())).lastrowid
        return rule_id

    def update_rule(self, rule_id, paused):
        if not isinstance(paused, bool):
            raise ValueError("暫停狀態不正確")
        with self.scan_lock, self.db() as conn:
            row = conn.execute("UPDATE rules SET paused=?,next_run=? WHERE id=?", (paused, self.clock(), rule_id))
            if not row.rowcount:
                raise ValueError("找不到掃描條件")

    def delete_rule(self, rule_id):
        with self.scan_lock, self.db() as conn:
            row = conn.execute("DELETE FROM rules WHERE id=?", (rule_id,))
            if not row.rowcount:
                raise ValueError("找不到掃描條件")

    def scan(self, rule_id, scheduled=False):
        with self.scan_lock:
            with self.db() as conn:
                row = conn.execute("SELECT * FROM rules WHERE id=?", (rule_id,)).fetchone()
            if row is None:
                raise ValueError("找不到掃描條件")
            if scheduled and (row["paused"] or row["next_run"] > self.clock()):
                return None
            found, statuses = self.search_all(json.loads(row['filters']))
            warnings = [{"source": s["name"], "error": s["error"]} for s in statuses if s["error"]]
            now, new_count = self.clock(), 0
            with self.db() as conn:
                for job in found:
                    conn.execute("INSERT INTO jobs(id,source,payload,active) VALUES(?,?,?,1) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,active=1", (job['id'],job['source'],json.dumps(job,ensure_ascii=False)))
                    new_count += conn.execute("INSERT OR IGNORE INTO discoveries(rule_id,job_id,discovered_at) VALUES(?,?,?)", (rule_id, job["id"], now)).rowcount
                conn.execute("INSERT INTO runs(rule_id,ran_at,matches,new_count,warnings) VALUES(?,?,?,?,?)", (rule_id, now, len(found), new_count, json.dumps(warnings)))
                conn.execute("UPDATE rules SET last_run=?,next_run=? WHERE id=?", (now, now + row["hours"] * 3600, rule_id))
            return {"matches": len(found), "new_count": new_count, "warnings": warnings}

    def discoveries(self, rule_id):
        with self.db() as conn:
            rows = conn.execute("SELECT j.payload,j.active,d.discovered_at,r.name AS rule_name FROM discoveries d JOIN jobs j ON j.id=d.job_id JOIN rules r ON r.id=d.rule_id WHERE d.rule_id=? ORDER BY d.discovered_at DESC", (rule_id,)).fetchall()
        return [json.loads(row["payload"]) | {"active": bool(row["active"]), "discovered_at": row["discovered_at"], "rule_name": row["rule_name"]} for row in rows]

    def tick(self):
        for rule in self.rules():
            if not rule["paused"] and rule["next_run"] <= self.clock():
                self.scan(rule["id"], scheduled=True)

    def start(self):
        def loop():
            while not self.stop.is_set():
                try:
                    self.tick()
                except Exception:
                    import logging
                    logging.exception("Background scan failed; retry on next tick")
                self.stop.wait(30)
        thread = threading.Thread(target=loop, name="workapp-scheduler", daemon=True)
        thread.start()
        return thread
