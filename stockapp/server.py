"""Local-only quote proxy; never transmits holdings or costs upstream."""
import json, math, re, threading, time, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
try:
    from .analysis import analyze, RESULT_CACHE
    from .market_calendar import load_calendar, is_session, previous_session, context as calendar_context
    from .update_market_data import refresh as refresh_market_data
    from .corporate_actions import snapshot as action_snapshot
except ImportError:
    from analysis import analyze, RESULT_CACHE
    from market_calendar import load_calendar, is_session, previous_session, context as calendar_context
    from update_market_data import refresh as refresh_market_data
    from corporate_actions import snapshot as action_snapshot
TZ=timezone(timedelta(hours=8))
LOCK=threading.Lock()
CACHE={}
MARKET_UPDATE_LOCK=threading.Lock()
MARKET_LAST_ATTEMPT=0
MARKET_LAST_ERROR=''
def update_market_background():
    global MARKET_LAST_ERROR
    if not MARKET_UPDATE_LOCK.acquire(blocking=False):return
    try:
        result=refresh_market_data();CACHE.clear();RESULT_CACHE.clear();MARKET_LAST_ERROR='部分來源更新失敗' if result['errors'] else ''
    except Exception:MARKET_LAST_ERROR='官方資料更新失敗，保留既有快照'
    finally:MARKET_UPDATE_LOCK.release()

def fetch_market_snapshot():
    with LOCK:
        old=CACHE.get('market-snapshot')
        if old and time.monotonic()-old[0]<300:return old[1]
    quotes=[];errors=[]
    for exchange,url in [('tse','https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL'),('otc','https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes')]:
        try:
            with urllib.request.urlopen(url,timeout=25) as response:rows=json.loads(response.read().decode('utf-8'))
            for row in rows:
                sid=row.get('Code') or row.get('SecuritiesCompanyCode')
                if not re.fullmatch(r'[0-9]{4,6}[A-Z]?',sid or ''):continue
                close=number(row.get('ClosingPrice') or row.get('Close'))
                try:delta=float(str(row.get('Change','')).replace(',',''))
                except ValueError:continue
                raw=str(row.get('Date','')).strip()
                if len(raw)!=7 or not raw.isdigit():continue
                date=f'{int(raw[:3])+1911:04d}-{raw[3:5]}-{raw[5:]}'
                if close and math.isfinite(delta) and close-delta>0:
                    quotes.append(dict(id=sid,exchange=exchange,date=date,change=delta/(close-delta)*100))
        except Exception:errors.append(exchange)
    if not quotes:raise ValueError('market data unavailable')
    result=dict(quotes=quotes,errors=errors,fetchedAt=datetime.now(TZ).isoformat())
    with LOCK:CACHE['market-snapshot']=(time.monotonic(),result)
    return result
def number(v):
    try:
        v=float(v)
        return v if math.isfinite(v) and v>0 else None
    except (TypeError,ValueError): return None
def normalize(row,now=None,calendar=None):
    now=now or datetime.now(TZ)
    price,previous=number(row.get('z')),number(row.get('y'))
    try: stamp=datetime.strptime(row.get('d','')+' '+row.get('t',''),'%Y%m%d %H:%M:%S').replace(tzinfo=TZ)
    except ValueError: stamp=None
    session=is_session(now.date(),calendar) if calendar is not None else now.weekday()<5
    opened=session is True and '09:00'<=now.strftime('%H:%M')<'13:30'
    status='no_trade' if price is None else 'stale' if not stamp or stamp.date()!=now.date() else ('active' if (now-stamp).total_seconds()<=180 else 'stale') if opened else 'last_trade'
    if price and stamp and stamp.date()<now.date() and (session is False or (session is True and now.strftime('%H:%M')<'09:00')):
        if calendar is not None:previous_day=previous_session(now.date(),calendar)
        else:
            previous_day=now.date()-timedelta(days=1)
            while previous_day.weekday()>=5:previous_day-=timedelta(days=1)
        if stamp.date()==previous_day and stamp.strftime('%H:%M')>='13:30':status='previous_close'
    if calendar is not None and session is None:status='calendar_unknown'
    if calendar is not None and price and stamp and is_session(stamp.date(),calendar) is False:status='calendar_conflict'
    valuation_eligible=bool(status=='stale' and session is False and stamp and price and 0<(now.date()-stamp.date()).days<=7 and stamp.strftime('%H:%M')>='13:30' and calendar is not None and is_session(stamp.date(),calendar) is True)
    expected_day=previous_session(now.date(),calendar) if calendar else None
    try:
        volume=float(row.get('v',''))*1000
        if not math.isfinite(volume) or volume<0:volume=None
    except (ValueError,TypeError):volume=None
    return dict(valuationEligible=valuation_eligible,expectedQuoteDate=expected_day.isoformat() if expected_day else None,volumeShares=volume,id=row.get('c'),name=row.get('n') or row.get('c'),exchange=row.get('ex'),price=price,previous=previous,change=(price/previous-1)*100 if price and previous else None,open=number(row.get('o')),high=number(row.get('h')),low=number(row.get('l')),quotedAt=stamp.isoformat() if stamp else None,status=status)
def fetch_quotes(ids):
    key=tuple(sorted(ids))
    with LOCK:
        old=CACHE.get(key)
        if old and time.monotonic()-old[0]<10:return old[1]
        channels=[]
        for sid in ids:
            channels.extend(['tse_t00.tw'] if sid=='t00' else ['otc_o00.tw'] if sid=='o00' else ['tse_'+sid+'.tw','otc_'+sid+'.tw'])
        url='https://mis.twse.com.tw/stock/api/getStockInfo.jsp?'+urllib.parse.urlencode(dict(ex_ch='|'.join(channels),json=1,delay=0))
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://mis.twse.com.tw/stock/index.jsp'})
        with urllib.request.urlopen(req,timeout=12) as response:payload=json.loads(response.read().decode('utf-8'))
        if payload.get('rtcode')!='0000':raise ValueError('upstream error')
        rows={};calendar=load_calendar() or {}
        for row in payload.get('msgArray',[]):
            if row.get('c') in ids:
                q=normalize(row,calendar=calendar)
                if q['id'] not in rows or q['price'] is not None:rows[q['id']]=q
        result=dict(quotes=list(rows.values()),missing=[sid for sid in ids if sid not in rows],fetchedAt=datetime.now(TZ).isoformat(),source='TWSE MIS',refreshSeconds=15,delayGuarantee=False)
        CACHE[key]=(time.monotonic(),result)
        return result
class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Keep the origin/storage stable while ensuring app updates are visible on reload.
        if urllib.parse.urlsplit(self.path).path=='/classifications.json':
            self.send_header('Cache-Control','public, max-age=300')
        elif not urllib.parse.urlsplit(self.path).path.startswith('/api/'):
            self.send_header('Cache-Control','no-store')
        super().end_headers()
    def do_GET(self):
        global MARKET_LAST_ATTEMPT
        parsed=urllib.parse.urlsplit(self.path)
        if parsed.path=='/api/market-context':
            update=None
            if urllib.parse.parse_qs(parsed.query).get('refresh')==['1']:
                if not MARKET_UPDATE_LOCK.acquire(blocking=False):return self.respond(409,{'error':'資料更新中，請稍後查看。'})
                try:
                    update=refresh_market_data();CACHE.clear();RESULT_CACHE.clear()
                except Exception:return self.respond(502,{'error':'官方日曆／公司行動更新失敗，保留既有來源資料。'})
                finally:MARKET_UPDATE_LOCK.release()
            ctx=calendar_context();actions=action_snapshot()
            stale=True
            try:stale=(datetime.now(TZ)-datetime.fromisoformat(actions['fetchedAt'])).total_seconds()>86400
            except (TypeError,ValueError,KeyError):pass
            if stale and time.monotonic()-MARKET_LAST_ATTEMPT>300:
                MARKET_LAST_ATTEMPT=time.monotonic();threading.Thread(target=update_market_background,daemon=True).start()
            ctx['updating']=MARKET_UPDATE_LOCK.locked();ctx['lastUpdateError']=MARKET_LAST_ERROR;ctx['actions']={k:actions.get(k) for k in ['fetchedAt','historyFrom','historyTo','sources','errors','sourceStatus','lastAttemptAt','otcHistoryFrom','otcHistoryTo']};ctx['update']=update
            return self.respond(200,ctx)
        if parsed.path=='/api/market-snapshot':
            try:return self.respond(200,fetch_market_snapshot())
            except Exception:return self.respond(502,{'error':'族群收盤資料暫時無法取得。'})
        if parsed.path=='/api/analysis':
            args=urllib.parse.parse_qs(parsed.query)
            sid=args.get('id',[''])[0];exchange=args.get('exchange',[''])[0]
            if not re.fullmatch(r'[0-9]{4,6}[A-Z]?',sid) or exchange not in ['tse','otc']:
                return self.respond(400,{'error':'請提供有效股票代碼與交易市場。'})
            try:return self.respond(200,analyze(sid,exchange))
            except Exception:return self.respond(502,{'error':'分析來源暫時無法取得，請稍後重試；未產生示範分析。'})
        if parsed.path!='/api/quotes':return super().do_GET()
        ids=list(dict.fromkeys(urllib.parse.parse_qs(parsed.query).get('ids',[''])[0].split(',')))
        if len(ids)>40 or not all(re.fullmatch(r'(?:[0-9]{4,6}[A-Z]?|t00|o00)',sid) for sid in ids):return self.respond(400,{'error':'請使用有效台股代碼，每次最多 40 檔。'})
        try:self.respond(200,fetch_quotes(ids))
        except Exception:self.respond(502,{'error':'行情來源暫時無法回應，請稍後重試；不使用示範价格補值。'})
    def respond(self,status,payload):
        body=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)
if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',8765),partial(Handler,directory=str(Path(__file__).parent)))
    print('ClearSignal: http://127.0.0.1:8765',flush=True)
    server.serve_forever()
