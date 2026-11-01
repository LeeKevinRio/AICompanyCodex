"""US public research quotes; no portfolio inputs or orders."""
import re, math, urllib.request, json, time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TICKER = re.compile(r'[A-Z]{1,6}(?:[.-][A-Z]{1,2})?')
CACHE = {}

def number(v):
    return float(v) if type(v) in [int, float] and math.isfinite(v) else None

def parse_chart(payload, symbol, now=None):
    now = now or datetime.now(timezone.utc)
    data = payload['chart']['result'][0]; m = data['meta']
    if m.get('symbol') != symbol or m.get('currency') != 'USD' or m.get('exchangeName') not in ['NMS','NGM','NCM','NYQ','ASE','PCX','BTS','BATS'] or m.get('instrumentType') not in ['EQUITY','ETF']:
        raise ValueError('只支援可核對美元美股／ETF')
    price = number(m.get('regularMarketPrice')); stamp = number(m.get('regularMarketTime'))
    if price is None or price <= 0 or stamp is None or stamp > now.timestamp()+300:
        raise ValueError('行情無有效價格或時間')
    if now.timestamp()-stamp > 86400*7: raise ValueError('來源行情超過7日，暫停估值')
    quote = data['indicators']['quote'][0]; bars = []
    for i, ts in enumerate(data.get('timestamp', [])):
        close = number((quote.get('close') or [])[i]); vol = number((quote.get('volume') or [])[i])
        if close is not None and close > 0 and ts <= now.timestamp()+300:
            bars.append(dict(date=datetime.fromtimestamp(ts,timezone.utc).astimezone(ZoneInfo('America/New_York')).date().isoformat(), close=close, volume=vol))
    if not bars: raise ValueError('沒有可核對的價格日線')
    day = datetime.fromtimestamp(stamp,timezone.utc).astimezone(ZoneInfo('America/New_York')).date().isoformat()
    prior = next((b['close'] for b in reversed(bars) if b['date'] < day),None)
    periods = m.get('currentTradingPeriod',{}).get('regular',{}); start=periods.get('start'); end=periods.get('end')
    state = '正常盤進行中' if start and end and start <= now.timestamp() < end else '正常盤外／最近正常盤參考'
    return dict(symbol=symbol,name=m.get('longName') or m.get('shortName') or symbol,exchange=m['exchangeName'],currency='USD',type=m['instrumentType'],price=price,previous=prior,change=(price/prior-1)*100 if prior else None,quotedAt=datetime.fromtimestamp(stamp,timezone.utc).isoformat(),marketDate=day,marketState=state,bars=bars,source='https://finance.yahoo.com/quote/'+symbol+'/',provider='Yahoo Finance',delayNote='第三方公開行情，延遲與服務可用性不保證；不含盤前盤後成交',fetchedAt=now.isoformat(),forecastEnabled=False)

def quote(symbol):
    symbol = str(symbol).upper()
    if not TICKER.fullmatch(symbol): raise ValueError('請輸入有效美股代碼')
    cached = CACHE.get(symbol)
    if cached and time.monotonic()-cached[0] < 60: return cached[1]
    url = 'https://query1.finance.yahoo.com/v8/finance/chart/'+symbol+'?interval=1d&range=6mo&events=div%2Csplits'
    request = urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(request,timeout=18) as r: payload=json.load(r)
    result=parse_chart(payload,symbol); CACHE[symbol]=(time.monotonic(),result)
    return result
