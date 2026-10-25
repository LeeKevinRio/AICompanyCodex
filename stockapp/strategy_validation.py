"""Frozen-rule chronological holdout diagnostic; not certified out-of-sample alpha."""
def validate(bars,indicator,events=(),cost_percent=.5):
    if not 0<=cost_percent<=10:raise ValueError('Invalid roundtrip cost')
    split=60+int(max(0,len(bars)-60)*.7)
    reports=[]
    for horizon in (3,5):
        equity=1.;peak=1.;drawdown=0.;trades=[];windows=[];excluded=0
        for i in range(split,len(bars)-horizon,horizon):
            entry=bars[i+1];exit=bars[i+horizon]
            if any(bars[i]['date']<e['date']<=exit['date'] for e in events):excluded+=1;continue
            if not entry.get('open') or entry['open']<=0:excluded+=1;continue
            signal=indicator(bars[:i+1]);ret=exit['close']/entry['open']-1
            active=bool(signal and signal['bias']=='偏多')
            net=ret-cost_percent/100 if active else 0
            if active:trades.append(dict(signalDate=bars[i]['date'],entryDate=entry['date'],exitDate=exit['date'],grossReturn=ret*100,netReturn=net*100))
            windows.append(dict(entryDate=entry['date'],exitDate=exit['date'],baselineReturn=ret-cost_percent/100))
            equity*=1+net;peak=max(peak,equity);drawdown=min(drawdown,equity/peak-1)
        baseline=1.
        for w in windows:baseline*=1+w['baselineReturn']
        reports.append(dict(days=horizon,windowCount=len(windows),tradeCount=len(trades),excludedWindows=excluded,netReturn=(equity-1)*100,alwaysEnterReturn=(baseline-1)*100,maxExitDrawdown=-drawdown*100,winRate=sum(t['netReturn']>0 for t in trades)/len(trades)*100 if trades else None,trades=trades,firstDate=windows[0]['entryDate'] if windows else None,lastDate=windows[-1]['exitDate'] if windows else None))
    return dict(method='固定v4規則／末段30%留出檢查，未經獨立樣本外驗證',costPercent=cost_percent,splitDate=bars[split]['date'] if split<len(bars) else None,reports=reports,limitations=['偏多才進場，其餘持現金；訊號隔日開盤進、天期末收盤出，不做放空。','每筆等比例全額再投入，未模擬整張限制、跳空停損或流動性。','來回0.5%僅示範成本假設，不是實際稅費；同窗固定進場採相同成本。','回撤只在出場點量測，非完整持倉期間最大回撤。','目前規則曾被檢視，留出區不代表真正未見資料；未計含息總報酬。'])
