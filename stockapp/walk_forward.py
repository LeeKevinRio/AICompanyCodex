"""Historical replay: build predictions from each prefix before scoring outcomes."""
from datetime import date
try:
    from .corporate_actions import adjust
    from .market_calendar import next_sessions
except ImportError:
    from corporate_actions import adjust
    from market_calendar import next_sessions

def replay(bars,indicator,calendar,events=(),days=90):
    if not isinstance(days,int) or not 1<=days<=365:raise ValueError('Invalid replay length')
    predictions=[]
    start=max(59,len(bars)-days)
    # Phase 1 never reads a future bar or a future action to choose a direction.
    for i in range(start,len(bars)):
        raw=[dict(b) for b in bars[:i+1]]
        asof=raw[-1]['date'];known=[e for e in events if e['date']<=asof]
        prefix,applied,unresolved=adjust(raw,known)
        matched={e['date'] for e in applied};cut=0
        for j in range(1,len(prefix)):
            gap=(date.fromisoformat(prefix[j]['date'])-date.fromisoformat(prefix[j-1]['date'])).days
            if abs(prefix[j]['close']/prefix[j-1]['close']-1)>.3 or gap>20 or ('**' in prefix[j].get('note','') and prefix[j]['date'] not in matched):cut=j
        technical=indicator(prefix[cut:]) if not unresolved else None
        predictions.append(dict(asOf=asof,inputThrough=asof,inputCount=len(prefix[cut:]),baseClose=raw[-1]['close'],bias=technical['bias'] if technical else None,score=technical['score'] if technical else None,reason='公司行動需核對' if unresolved else '歷史不足60筆' if not technical else None))
    # Phase 2 may inspect future observations only to judge the already-fixed prediction.
    by_date={b['date']:b for b in bars};reports=[]
    for horizon in (3,5):
        rows=[]
        for p in predictions:
            row={**p,'days':horizon,'status':'等待到期','return':None,'hit':None,'realized':None}
            expected=next_sessions(date.fromisoformat(p['asOf']),horizon,calendar)
            row['endDate']=expected[-1] if expected else None
            if not p['bias']:row['status']='不評估：'+(p['reason'] or '訊號不明，觀察')
            elif not expected:row['status']='交易日曆不足'
            elif any(d not in by_date for d in expected):row['status']='缺指定日線' if bars[-1]['date']>=expected[-1] else '等待到期'
            elif any(p['asOf']<e['date']<=expected[-1] for e in events):row['status']='跨公司行動，排除'
            else:
                previous=p['baseClose'];valid=previous>0
                for d in expected:
                    b=by_date[d]
                    if b['close']<=0 or abs(b['close']/previous-1)>.3 or '**' in b.get('note',''):valid=False
                    previous=b['close']
                if not valid:row['status']='價格尺度異常，排除'
                else:
                    value=(by_date[expected[-1]]['close']/p['baseClose']-1)*100
                    realized='偏多' if value>.5 else '偏空' if value<-.5 else '震盪'
                    row.update(status='已核對',return_=value,realized=realized,hit=realized==p['bias'])
                    row['return']=row.pop('return_')
            rows.append(row)
        done=[r for r in rows if r['status']=='已核對'];n=len(done)
        hits=sum(r['hit'] for r in done)
        reports.append(dict(days=horizon,total=len(rows),done=n,hits=hits,misses=n-hits,pending=sum(r['status']=='等待到期' for r in rows),excluded=sum(r['status'] not in ['等待到期','已核對'] for r in rows),hitRate=hits/n*100 if n else None,alwaysUpRate=sum(r['realized']=='偏多' for r in done)/n*100 if n else None,alwaysDownRate=sum(r['realized']=='偏空' for r in done)/n*100 if n else None,rows=rows))
    return dict(model='透明規則v4／逐日歷史重播',requestedDays=days,anchorCount=len(predictions),fromDate=predictions[0]['asOf'] if predictions else None,toDate=predictions[-1]['asOf'] if predictions else None,reports=reports,limitations=['每次只把當日及以前日線與已發生公司行動傳入規則；未使用現在財報或新聞推回過去。','歷史重播不寫入真實預測日誌，不冒充當時已發布的預測。','v4曾在目前資料上被設計與檢視，並非真正封存未見樣本外實驗；歷史來源也可能事後修正。','每日3／5日窗口重疊，樣本並不獨立；命中率不等於含成本交易獲利。','未納入歷史當時已公告但尚未發生的事件；跨公司行動在結果核對階段排除。'])
