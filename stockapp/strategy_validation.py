"""Frozen-rule chronological holdout diagnostic; not certified out-of-sample alpha."""
from datetime import date
try:
    from .historical_evaluation import observations,non_overlapping
    from .market_calendar import load_calendar,next_sessions
except ImportError:
    from historical_evaluation import observations,non_overlapping
    from market_calendar import load_calendar,next_sessions


def validate(bars,indicator,events=(),cost_percent=.5,calendar=None):
    if not 0<=cost_percent<=10:raise ValueError('Invalid roundtrip cost')
    split=60+int(max(0,len(bars)-60)*.7)
    calendar=load_calendar() if calendar is None else calendar
    replay_reports=observations(bars,indicator,calendar,events)
    by_date={b['date']:b for b in bars};split_date=bars[split]['date'] if split<len(bars) else None
    reports=[]
    for horizon in (3,5):
        equity=1.;peak=1.;drawdown=0.;trades=[];windows=[];excluded=0;pending=0
        rows=next(r['rows'] for r in replay_reports if r['days']==horizon)
        slots=non_overlapping([r for r in rows if split_date and r['asOf']>=split_date])
        for row in slots:
            if row['status']!='已核對':
                if row['status']=='等待到期':pending+=1
                else:excluded+=1
                continue
            expected=next_sessions(date.fromisoformat(row['asOf']),horizon,calendar)
            entry=by_date[expected[0]];exit=by_date[expected[-1]]
            if not entry.get('open') or entry['open']<=0:excluded+=1;continue
            ret=exit['close']/entry['open']-1
            active=row['bias']=='偏多'
            net=ret-cost_percent/100 if active else 0
            if active:trades.append(dict(signalDate=row['asOf'],entryDate=entry['date'],exitDate=exit['date'],grossReturn=ret*100,netReturn=net*100))
            windows.append(dict(entryDate=entry['date'],exitDate=exit['date'],baselineReturn=ret-cost_percent/100))
            equity*=1+net;peak=max(peak,equity);drawdown=min(drawdown,equity/peak-1)
        baseline=1.
        for w in windows:baseline*=1+w['baselineReturn']
        reports.append(dict(days=horizon,windowCount=len(windows),tradeCount=len(trades),excludedWindows=excluded,pendingWindows=pending,netReturn=(equity-1)*100,alwaysEnterReturn=(baseline-1)*100,maxExitDrawdown=-drawdown*100,winRate=sum(t['netReturn']>0 for t in trades)/len(trades)*100 if trades else None,trades=trades,firstDate=windows[0]['entryDate'] if windows else None,lastDate=windows[-1]['exitDate'] if windows else None))
    return dict(method='固定v4規則／末段30%指定交易日檢查，未經獨立樣本外驗證',evaluationVersion='scheduled-window-v1',costPercent=cost_percent,splitDate=split_date,reports=reports,limitations=['偏多才進場，其餘持現金；訊號次一指定交易日開盤進、天期末指定收盤出，不做放空。','缺指定日線、跨公司行動及價格尺度異常排除，不以後續日線補足天期。','各訊號只使用當日以前原始日線及已發生公司行動；不是以今天的還原序列回填。','每筆等比例全額再投入，未模擬整張限制、跳空停損或流動性。','來回0.5%僅示範成本假設，不是實際稅費；同窗固定進場採相同成本。','回撤只在出場點量測，非完整持倉期間最大回撤。','目前規則曾被檢視，留出區不代表真正未見資料；未計含息總報酬。'])
