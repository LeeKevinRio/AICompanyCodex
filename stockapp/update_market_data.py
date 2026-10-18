"""Refresh public schedule/actions. No account or portfolio data."""
import concurrent.futures,json,urllib.request
from datetime import datetime,timedelta
from pathlib import Path
try:
    from .market_calendar import SOURCE,FILE,parse_schedule,iso_date,TZ,load_calendar,merge_schedules
except ImportError:
    from market_calendar import SOURCE,FILE,parse_schedule,iso_date,TZ,load_calendar,merge_schedules

def numeric(v):
    try:return float(str(v).replace(',',''))
    except (ValueError,TypeError):return None

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=25) as r:return json.loads(r.read().decode('utf-8-sig'))

def write_json(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    temporary.replace(path)

def source_key(url):
    return url.split('?')[0]

def merge_action_snapshot(old,new,failed,stamp):
    """Retain only failed source families; a successful empty result removes old events."""
    failed_keys={source_key(u) for u in failed}
    kept=[e for e in old.get('events',[]) if source_key(e.get('source','')) in failed_keys]
    events={(e['exchange'],e['id'],e['date']):e for e in kept}
    for e in new.get('events',[]):
        key=(e['exchange'],e['id'],e['date'])
        if key not in events or e.get('referencePrice') or not events[key].get('referencePrice'):events[key]=e
    result={**new,'events':list(events.values()),'lastAttemptAt':stamp}
    if failed_keys:
        # Never relabel retained old records as freshly fetched.
        result['fetchedAt']=old.get('fetchedAt')
        result['sources']=list(dict.fromkeys(old.get('sources',[])+new.get('sources',[])))
        if any('TWT49U' in u for u in failed_keys):
            result['historyFrom']=old.get('historyFrom');result['historyTo']=old.get('historyTo')
    return result

def refresh():
    now=datetime.now(TZ);start=(now.date()-timedelta(days=400)).replace(day=1);today=now.date();stamp=now.isoformat()
    historic=f'https://www.twse.com.tw/rwd/zh/exRight/TWT49U?startDate={start:%Y%m%d}&endDate={today:%Y%m%d}&response=json'
    upcoming='https://openapi.twse.com.tw/v1/exchangeReport/TWT48U_ALL'
    otc='https://www.tpex.org.tw/openapi/v1/tpex_exright_daily'
    otc_next='https://www.tpex.org.tw/openapi/v1/tpex_exright_prepost'
    urls=[SOURCE,historic,upcoming,otc,otc_next];data={};errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(fetch,u):u for u in urls}
        for f,u in futures.items():
            try:data[u]=f.result()
            except Exception:errors.append(u)
    if SOURCE in data:
        try:
            calendar=parse_schedule(data[SOURCE]);calendar['fetchedAt']=stamp;calendar=merge_schedules(load_calendar(),calendar)
            write_json(FILE,dict(version=1,calendar=calendar))
        except (ValueError,TypeError,KeyError):
            errors.append(SOURCE);data.pop(SOURCE,None)
    for u in [upcoming,otc,otc_next]:
        if u in data and (not isinstance(data[u],list) or any(not isinstance(r,dict) for r in data[u])):
            errors.append(u);data.pop(u,None)
    events={}
    def add(e):
        if not e['date'] or not e['id']:return
        key=(e['exchange'],e['id'],e['date'])
        if key not in events or e.get('referencePrice'):events[key]=e
    h=data.get(historic,{})
    if not isinstance(h,dict):h={}
    if h.get('stat')=='OK':
        for r in h.get('data',[]):
            if len(r)>=7:add(dict(id=r[1],date=iso_date(r[0]),exchange='tse',kind=r[6],previousClose=numeric(r[3]),referencePrice=numeric(r[4]),source=historic))
    else:
        if historic not in errors:errors.append(historic)
    for r in data.get(upcoming,[]):add(dict(id=r.get('Code'),date=iso_date(r.get('Date')),exchange='tse',kind=r.get('Exdividend','除權息'),cashDividend=numeric(r.get('CashDividend')),source=upcoming))
    for r in data.get(otc,[]):add(dict(id=r.get('SecuritiesCompanyCode'),date=iso_date(r.get('Date')),exchange='otc',kind=r.get('ExRightsDiviend','除權息'),previousClose=numeric(r.get('ClosePriceBeforeExRightsDiviend')),referencePrice=numeric(r.get('ExRightsDiviendQuote')),source=otc))
    for r in data.get(otc_next,[]):add(dict(id=r.get('SecuritiesCompanyCode'),date=iso_date(r.get('ExRrightsExDividendDate')),exchange='otc',kind=r.get('ExRrightsExDividend','除權息'),source=otc_next))
    action_file=Path(__file__).with_name('corporate-actions.json')
    try:old=json.loads(action_file.read_text(encoding='utf-8'))
    except (OSError,ValueError):old={}
    if events or old or any(u in data for u in [historic,upcoming,otc,otc_next]):
        out=dict(version=1,fetchedAt=stamp,historyFrom=start.isoformat() if historic not in errors else None,historyTo=today.isoformat() if historic not in errors else None,events=list(events.values()),sources=list(data),errors=errors)
        out=merge_action_snapshot(old,out,[u for u in errors if u!=SOURCE],stamp)
        write_json(action_file,out)
    return dict(fetchedAt=stamp,eventCount=len(events),errors=errors,calendarUpdated=SOURCE in data)

if __name__=='__main__':print(json.dumps(refresh(),ensure_ascii=False))
