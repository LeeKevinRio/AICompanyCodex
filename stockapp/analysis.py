"""Transparent market analysis from public exchange data; no account data."""
import concurrent.futures
import json
import math
import statistics
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
try:
    from .strategy_validation import validate as validate_strategy
    from .corporate_actions import for_stock, adjust
    from .market_calendar import load_calendar, next_sessions, is_session
except ImportError:
    from strategy_validation import validate as validate_strategy
    from corporate_actions import for_stock, adjust
    from market_calendar import load_calendar, next_sessions, is_session
TZ=timezone(timedelta(hours=8))
DATA_CACHE={}
RESULT_CACHE={}
DATA_LOCK=threading.Lock()
RESULT_LOCK=threading.Lock()

def numeric(v):
    try:
        n=float(str(v).replace(',','').replace(' ','').strip())
        return n if math.isfinite(n) else None
    except (ValueError,TypeError):return None

def roc_date(value):
    value=str(value).strip()
    try:
        if '/' in value:
            y,m,d=map(int,value.split('/'))
            return datetime(y+1911 if y<1911 else y,m,d,tzinfo=TZ).date().isoformat()
        if len(value)==7:return datetime(int(value[:3])+1911,int(value[3:5]),int(value[5:]),tzinfo=TZ).date().isoformat()
        if len(value)==8:return datetime.strptime(value,'%Y%m%d').date().isoformat()
    except (ValueError,TypeError):pass
    return None

def fetch_json(url,ttl=3600):
    with DATA_LOCK:
        cached=DATA_CACHE.get(url)
        if cached and time.monotonic()-cached[0]<ttl:return cached[1]
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=18) as r:payload=json.loads(r.read().decode('utf-8-sig'))
    with DATA_LOCK:DATA_CACHE[url]=(time.monotonic(),payload)
    return payload

def parse_bars(payload,exchange):
    table=payload if exchange=='tse' else (payload.get('tables') or [{}])[0]
    fields=table.get('fields',[])
    bars=[]
    for row in table.get('data',[]):
        if len(row)<7:continue
        date=roc_date(row[0]);op,hi,lo,close=[numeric(v) for v in row[3:7]]
        volume=numeric(row[1])
        if not date or any(v is None or v<=0 for v in [op,hi,lo,close]) or not (lo<=close<=hi and lo<=op<=hi):continue
        if exchange=='otc' and '張' in ''.join(fields[:2]):volume=volume*1000 if volume is not None else None
        bars.append(dict(date=date,open=op,high=hi,low=lo,close=close,volume=volume,note=str(row[9]) if len(row)>9 else ''))
    return bars

def history(sid,exchange,now=None):
    now=now or datetime.now(TZ)
    total=now.year*12+now.month-1
    months=[(total-i)//12*100+((total-i)%12+1) for i in range(12)]
    def one(month):
        if exchange=='tse':url='https://www.twse.com.tw/exchangeReport/STOCK_DAY?'+urllib.parse.urlencode(dict(response='json',date=str(month)+'01',stockNo=sid))
        else:url='https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock?'+urllib.parse.urlencode(dict(code=sid,date=f'{month//100}/{month%100:02d}/01',response='json'))
        return parse_bars(fetch_json(url,ttl=1800 if month==months[0] else 86400),exchange),url
    bars=[];sources=[];failures=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for future in [pool.submit(one,m) for m in months]:
            try:
                rows,url=future.result();bars.extend(rows);sources.append(url)
            except Exception:failures+=1
    # Intraday daily totals are incomplete; exclude today's bar until regular closing.
    today=now.date().isoformat()
    calendar=load_calendar()
    bars=sorted({b['date']:b for b in bars if is_session(datetime.fromisoformat(b['date']).date(),calendar) is not False and (b['date']<today or (b['date']==today and now.hour*60+now.minute>=14*60+30))}.values(),key=lambda b:b['date'])
    if not bars:raise ValueError('沒有可用的日線資料')
    return bars,sources,failures

def ema(values,period):
    if not values:return []
    output=[values[0]];a=2/(period+1)
    for v in values[1:]:output.append(v*a+output[-1]*(1-a))
    return output

def compare_signal(a,b,scale=0):
    # Numerical tolerance only; not a tuned trading threshold.
    tolerance=max(abs(a),abs(b),abs(scale),1)*1e-9
    return 1 if a-b>tolerance else -1 if b-a>tolerance else 0

def indicators(bars):
    if len(bars)<60:return None
    close=[b['close'] for b in bars];p=close[-1]
    ma={str(n):statistics.mean(close[-n:]) for n in [5,10,20,60]}
    gains=[max(close[i]-close[i-1],0) for i in range(1,len(close))]
    losses=[max(close[i-1]-close[i],0) for i in range(1,len(close))]
    ag,al=statistics.mean(gains[:14]),statistics.mean(losses[:14])
    for g,l in zip(gains[14:],losses[14:]):ag=(ag*13+g)/14;al=(al*13+l)/14
    rsi=50 if ag==al==0 else 100 if al==0 else 100-100/(1+ag/al)
    tr=[max(bars[i]['high']-bars[i]['low'],abs(bars[i]['high']-close[i-1]),abs(bars[i]['low']-close[i-1])) for i in range(1,len(bars))]
    atr=statistics.mean(tr[:14])
    for v in tr[14:]:atr=(atr*13+v)/14
    volumes=[b['volume'] for b in bars[-21:-1] if b['volume'] is not None]
    average_volume=statistics.mean(volumes) if len(volumes)==20 else None
    vr=bars[-1]['volume']/average_volume if bars[-1]['volume'] is not None and average_volume and average_volume>0 else None
    fast,slow=ema(close,12),ema(close,26);macd=[a-b for a,b in zip(fast,slow)];signal=ema(macd,9)
    score=50+15*compare_signal(p,ma['20'])+10*compare_signal(ma['5'],ma['20'])+10*compare_signal(ma['20'],ma['60'])+5*compare_signal(macd[-1],signal[-1],p)
    return5=(p/close[-6]-1)*100
    score+=10*compare_signal(p,ma['5'])+5*compare_signal(p,close[-6])
    if vr and vr>=1.5 and compare_signal(p,close[-2])<0:score-=15
    if rsi>=70:score-=5
    score=max(0,min(100,score))
    bias='偏多' if score>=65 else '偏空' if score<=35 else '震盪'
    reasons=[f"收盤 {'高於' if compare_signal(p,ma['20'])>0 else '低於' if compare_signal(p,ma['20'])<0 else '等於'} 20 日均線",f"5 日均線 {'高於' if compare_signal(ma['5'],ma['20'])>0 else '低於' if compare_signal(ma['5'],ma['20'])<0 else '等於'} 20 日均線",f"20 日均線 {'高於' if compare_signal(ma['20'],ma['60'])>0 else '低於' if compare_signal(ma['20'],ma['60'])<0 else '等於'} 60 日均線"]
    reasons.append(f"收盤 {'高於' if compare_signal(p,ma['5'])>0 else '低於' if compare_signal(p,ma['5'])<0 else '等於'} 5 日均線；5 日報酬 {return5:.2f}%")
    if vr and vr>=1.5 and compare_signal(p,close[-2])<0:reasons.append('放量下跌，短線風險分數扣15分')
    return dict(score=score,bias=bias,ma=ma,rsi=rsi,atr=atr,atrPercent=atr/p*100,return5=return5,volumeRatio=vr,macd=macd[-1],macdSignal=signal[-1],support=min(b['low'] for b in bars[-20:]),resistance=max(b['high'] for b in bars[-20:]),reasons=reasons,asOf=bars[-1]['date'])

def quantile(values,q):
    a=sorted(values);pos=(len(a)-1)*q;i=int(pos)
    return a[i]+(a[min(i+1,len(a)-1)]-a[i])*(pos-i)

def forecast(bars,current):
    result=[]
    for horizon in [3,5]:
        samples=[];all_returns=[];hits=0;predicted=0
        # Non-overlapping anchor dates per horizon. All features use only bars <= anchor.
        for i in range(59,len(bars)-horizon,horizon):
            past=indicators(bars[:i+1]);ret=bars[i+horizon]['close']/bars[i]['close']-1
            all_returns.append(ret)
            realized='偏多' if ret>.005 else '偏空' if ret<-.005 else '震盪'
            hits+=past['bias']==realized;predicted+=1
            if past['bias']==current['bias']:samples.append(ret)
        enough=len(samples)>=5
        hit=hits/predicted*100 if predicted>=30 else None
        baseline=sum(r>.005 for r in all_returns)/predicted*100 if predicted>=30 else None
        result.append(dict(days=horizon,bias=current['bias'],sampleCount=len(samples),evidence=('歷史參考' if len(samples)>=30 else '初步歷史區間') if enough else '同類樣本過少',medianReturn=quantile(samples,.5)*100 if enough else None,lowReturn=quantile(samples,.2)*100 if enough else None,highReturn=quantile(samples,.8)*100 if enough else None,reviewCount=predicted,reviewHitRate=hit,alwaysUpHitRate=baseline,validation='回顧樣本不足' if hit is None else '未優於偏多基準' if hit<=baseline else '回顧高於基準，仍待前瞻驗證',probability=None))
    return result

def get_field(row,*names):
    for name in names:
        if name in row:return row[name]
    return None

def fundamentals(sid,exchange):
    base='https://openapi.twse.com.tw/v1/opendata/' if exchange=='tse' else 'https://www.tpex.org.tw/openapi/v1/mopsfin_'
    suffix='_L' if exchange=='tse' else '_O'
    output=dict(revenue=None,financial=None,announcements=[],sources=[],errors=[],newsScore=None)
    def one(code):
        url=base+code+suffix
        return code,fetch_json(url,ttl=1800),url
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for future in [pool.submit(one,c) for c in ['t187ap05','t187ap14','t187ap04']]:
            try:
                code,rows,url=future.result();output['sources'].append(url)
                rows=[{k.strip():v for k,v in r.items()} for r in rows if get_field(r,'公司代號','SecuritiesCompanyCode')==sid]
                if code=='t187ap05' and rows:
                    r=max(rows,key=lambda r:str(r.get('資料年月','')))
                    output['revenue']=dict(period=r.get('資料年月'),amount=numeric(r.get('營業收入-當月營收')),yoy=numeric(r.get('營業收入-去年同月增減(%)')),mom=numeric(r.get('營業收入-上月比較增減(%)')),yearToDateYoY=numeric(r.get('累計營業收入-前期比較增減(%)')),publishedSnapshot=roc_date(get_field(r,'出表日期','Date')),unit='千元',source=url)
                elif code=='t187ap14' and rows:
                    r=max(rows,key=lambda r:(str(get_field(r,'年度','Year')),str(r.get('季別',''))))
                    output['financial']=dict(year=get_field(r,'年度','Year'),quarter=r.get('季別'),eps=numeric(get_field(r,'基本每股盈餘(元)','基本每股盈餘')),revenue=numeric(r.get('營業收入')),operatingProfit=numeric(r.get('營業利益')),netProfit=numeric(r.get('稅後淨利')),publishedSnapshot=roc_date(get_field(r,'出表日期','Date')),source=url,periodType='年度截至該季累計，不是單季')
                elif code=='t187ap04':
                    for r in rows:
                        title=r.get('主旨','');text=r.get('說明','')
                        output['announcements'].append(dict(title=title,date=roc_date(r.get('發言日期')),time=str(r.get('發言時間','')).zfill(6),factDate=roc_date(r.get('事實發生日')),text=text,source=url,riskFlag=any(word in title for word in ['暫停交易','停止買賣','變更交易方法','處置股票'])))
                    output['announcements'].sort(key=lambda a:(a['date'] or '',a['time']),reverse=True)
            except Exception:output['errors'].append('財務／公告來源暫時無法取得')
    rev,fin=output['revenue'],output['financial'];components=[]
    if rev and rev['yoy'] is not None:components.append(('營收年增率',max(0,min(100,50+rev['yoy']))))
    if fin and fin['eps'] is not None:components.append(('累計 EPS 正負',75 if fin['eps']>0 else 25 if fin['eps']<0 else 50))
    if fin and fin['netProfit'] is not None:components.append(('累計淨利正負',75 if fin['netProfit']>0 else 25 if fin['netProfit']<0 else 50))
    output['score']=round(statistics.mean(x[1] for x in components)) if len(components)>=2 else None
    output['scoreComponents']=[dict(name=n,score=s) for n,s in components]
    return output

def analyze(sid,exchange):
    key=(sid,exchange)
    with RESULT_LOCK:
        previous=RESULT_CACHE.get(key)
        if previous and time.monotonic()-previous[0]<1800:return previous[1]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        hf=pool.submit(history,sid,exchange);ff=pool.submit(fundamentals,sid,exchange)
        bars,sources,failed=hf.result();fund=ff.result()
    events,action_meta=for_stock(sid,exchange)
    adjusted_bars,applied,unresolved=adjust(bars,events)
    base_day=datetime.fromisoformat(bars[-1]['date']).date()
    forward=next_sessions(base_day,5,load_calendar())
    upcoming=[e for e in events if e['date'] in (forward or [])]
    alerts=[];last_break=-1
    matched_dates={e['date'] for e in applied}
    for i in range(1,len(adjusted_bars)):
        gap=(datetime.fromisoformat(adjusted_bars[i]['date'])-datetime.fromisoformat(adjusted_bars[i-1]['date'])).days
        if abs(adjusted_bars[i]['close']/adjusted_bars[i-1]['close']-1)>.3 or ('**' in adjusted_bars[i].get('note','') and adjusted_bars[i]['date'] not in matched_dates) or gap>20:last_break=i
    clean=adjusted_bars[last_break:] if last_break>=0 else adjusted_bars
    if last_break>=0:alerts.append('偵測到價格跳變／還原疑慮或超過20日資料缺口；指標與回顧只使用最近斷點之後資料。')
    if failed:alerts.append(f'{failed} 個月日線來源未完成，樣本可能不連續。')
    alerts.append('部分官方價格因子已還原，非完整公司行動還原；成交量保留原始股數。' if applied else '日線仍為原始價格或未取得可用還原因子，非完整還原股價。')
    if unresolved:alerts.append('公司行動因子缺漏、需人工核對或基準不一致，暫停情境及價位。')
    if upcoming:alerts.append('未來5交易日有已收錄公司行動，暫停跨事件價格情境及價位，請先核對事件。')
    if not action_meta.get('fetchedAt'):alerts.append('公司行動資料尚未取得，不代表沒有事件。')
    if forward is None:alerts.append('未來交易日曆涵蓋不足，日期仍待核對。')
    tech=indicators(clean)
    if not tech:alerts.append('可用完整日線不足60筆，暫停技術評分、趨勢與價位計算。')
    age=(datetime.now(TZ).date()-datetime.fromisoformat(bars[-1]['date']).date()).days
    if age>7:alerts.append('日線資料已超過7日，暫停趨勢及價位計算。')
    action_stale=True
    try:action_stale=(datetime.now(TZ)-datetime.fromisoformat(action_meta['fetchedAt'])).total_seconds()>172800
    except (TypeError,ValueError,KeyError):pass
    if action_stale:alerts.append('公司行動快照超過2日或未取得，暫停情境及價位；請更新官方資料。')
    coverage_start=action_meta.get('historyFrom' if exchange=='tse' else 'otcHistoryFrom');coverage_end=action_meta.get('historyTo' if exchange=='tse' else 'otcHistoryTo')
    coverage_failed=not coverage_start or coverage_start>bars[0]['date'] or not coverage_end or coverage_end<bars[-1]['date']
    if coverage_failed:alerts.append('所屬市場除權息歷史未涵蓋本段日線，暫停情境與價位。')
    if exchange=='otc':alerts.append('上櫃依已確認日期範圍還原除權息，拆股及減資仍未完整涵蓋。')
    can_predict=not coverage_failed and tech is not None and age<=7 and failed==0 and not unresolved and not upcoming and not action_stale and forward is not None
    if any(a['riskFlag'] for a in fund['announcements']):
        alerts.append('官方快照包含交易制度風險關鍵字，先核對公告；暫停價位計畫。')
        can_predict=False
    result=dict(pipelineVersion='calendar-actions-v4',id=sid,exchange=exchange,bars=bars[-120:],historyCount=len(clean),technical=tech,fundamental=fund,forecasts=forecast(clean,tech) if can_predict else [],alerts=alerts,planEnabled=can_predict,historySources=sources,asOf=bars[-1]['date'],fetchedAt=datetime.now(TZ).isoformat(),model='透明規則 v4（中性修正／部分公司行動還原）；尚未經前瞻驗證' if applied else '透明規則 v4（中性修正／原始價格）；尚未經前瞻驗證',adjusted=False,adjustment=dict(applied=bool(applied),events=applied,unresolved=unresolved,coverage=action_meta['coverage']),adjustedBars=adjusted_bars[-120:],corporateActions=events,actionMetadata=action_meta,nextSessions=forward)
    result['featureVersion']='integrated-v1'
    result['strategyValidation']=validate_strategy(clean,indicators,events) if not unresolved and not coverage_failed and not failed else None
    with RESULT_LOCK:RESULT_CACHE[key]=(time.monotonic(),result)
    return result
