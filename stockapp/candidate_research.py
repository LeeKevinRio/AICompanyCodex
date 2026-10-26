"""CR1 research. Candidate definitions fixed before this experiment; production untouched."""
import hashlib,json
from pathlib import Path
try:
    from .walk_forward import replay
except ImportError:
    from walk_forward import replay

SPEC=json.loads(Path(__file__).with_name('candidate-spec-v1.json').read_text(encoding='utf-8'))
SPEC_HASH=hashlib.sha256(json.dumps(SPEC,sort_keys=True,ensure_ascii=True).encode()).hexdigest()[:12]
ENGINE_HASH=hashlib.sha256(b''.join(Path(__file__).with_name(p).read_bytes() for p in ['candidate_research.py','walk_forward.py','analysis.py','corporate_actions.py'])).hexdigest()[:12]

def signal(rule,bars,indicator):
    t=indicator(bars)
    if not t:return None
    p=bars[-1]['close'];prev=bars[-2]['close'];atr=t['atr'];ma=t['ma'];vr=t['volumeRatio'];rsi=t['rsi'];bias=None
    if rule=='reversal3':
        if rsi<=30 and p<=ma['20']-.5*atr:bias='偏多'
        elif rsi>=70 and p>=ma['20']+.5*atr:bias='偏空'
    elif rule=='trend3' and vr is not None and vr>=1.2:
        if ma['5']>ma['20'] and p>max(b['high'] for b in bars[-4:-1]):bias='偏多'
        elif ma['5']<ma['20'] and p<min(b['low'] for b in bars[-4:-1]):bias='偏空'
    elif rule=='reversal5':
        if rsi<=35 and p<=ma['20']-1.5*atr and p>prev:bias='偏多'
        elif rsi>=65 and p>=ma['20']+1.5*atr and p<prev:bias='偏空'
    elif rule=='trend5' and vr is not None and vr>=1:
        if ma['20']>ma['60'] and p>ma['20'] and t['macd']>t['macdSignal']:bias='偏多'
        elif ma['20']<ma['60'] and p<ma['20'] and t['macd']<t['macdSignal']:bias='偏空'
    elif rule in ['selective3','selective5']:
        high,low=(85,15) if rule=='selective3' else (75,25)
        bias='偏多' if t['score']>=high else '偏空' if t['score']<=low else None
    return {**t,'bias':bias}

def summary(rows,baseline):
    eligible=[r for r in baseline if r['status']=='已核對'];allowed={r['asOf']:r for r in eligible}
    done=[r for r in rows if r['status']=='已核對' and r['asOf'] in allowed];n=len(done)
    hits=sum(r['hit'] for r in done)
    counts={b:sum(r['realized']==b for r in done) for b in ['偏多','偏空','震盪']}
    return dict(eligible=len(eligible),signals=n,abstentions=sum(r['asOf'] in allowed and not r['bias'] for r in rows),coverage=n/len(eligible) if eligible else 0,hits=hits,misses=n-hits,hitRate=hits/n*100 if n else None,constantRate=max(counts.values())/n*100 if n else None,v4Rate=sum(allowed[r['asOf']]['hit'] for r in done)/n*100 if n else None,edge=(hits-max(counts.values()))/n*100 if n else None)

def choose(training):
    qualified=[r for r in training if r['training']['signals']>=SPEC['minimumTrainingSignals'] and r['training']['coverage']>=SPEC['minimumCoverage'] and r['training']['edge'] is not None and r['training']['edge']>0]
    return sorted(qualified,key=lambda r:(-r['training']['edge'],-r['training']['coverage'],r['id']))[0]['id'] if qualified else None

def cost_diagnostic(rows,base,bars,cost):
    by_date={b['date']:i for i,b in enumerate(bars)};signals={r['asOf']:r for r in rows};equity=benchmark=peak=1.;dd=0.;trades=[];busy='';slots=0
    for r in base:
        if r['status']!='已核對' or r['asOf']<busy:continue
        i=by_date[r['asOf']];entry=bars[i+1];exit=bars[by_date[r['endDate']]]
        if not entry.get('open') or entry['open']<=0:continue
        busy=r['endDate'];slots+=1
        gross=(exit['close']/entry['open']-1)*100;benchmark*=1+(gross-cost)/100
        s=signals.get(r['asOf']);active=s and s['status']=='已核對' and s['bias']=='偏多'
        if active:trades.append(gross-cost);equity*=1+(gross-cost)/100
        peak=max(peak,equity);dd=max(dd,1-equity/peak)
    wins=[x for x in trades if x>0];losses=[x for x in trades if x<0]
    return dict(costPercent=cost,slots=slots,trades=len(trades),netReturn=(equity-1)*100,baselineReturn=(benchmark-1)*100,exitDrawdown=dd*100,averageWin=sum(wins)/len(wins) if wins else None,averageLoss=sum(losses)/len(losses) if losses else None,payoffRatio=(sum(wins)/len(wins))/abs(sum(losses)/len(losses)) if wins and losses else None)

def study(bars,indicator,calendar,events=()):
    current=bars
    # Freeze the historical split; new observations belong only to forward capture.
    bars=[b for b in bars if b['date']<=SPEC['historicalThrough']]
    start=max(59,len(bars)-SPEC['testAnchors']);cut=bars[start]['date'] if start<len(bars) else None
    full=replay(bars,indicator,calendar,events,days=max(1,min(365,len(bars)-59)))
    reports=[];forward=[]
    for horizon in (3,5):
        baseline=next(r['rows'] for r in full['reports'] if r['days']==horizon)
        train_base=[r for r in baseline if cut and r['asOf']<cut and r.get('endDate') and r['endDate']<cut]
        test_base=[r for r in baseline if cut and r['asOf']>=cut];results=[]
        for rule in [r for r in SPEC['rules'] if r['days']==horizon]:
            rr=replay(bars,lambda prefix:signal(rule['id'],prefix,indicator),calendar,events,days=max(1,min(365,len(bars)-59)))
            rows=next(r['rows'] for r in rr['reports'] if r['days']==horizon)
            train=[r for r in rows if cut and r['asOf']<cut and r.get('endDate') and r['endDate']<cut]
            test=[r for r in rows if cut and r['asOf']>=cut]
            results.append(dict(id=rule['id'],name=rule['name'],training=summary(train,train_base),review=summary(test,test_base),costs=[cost_diagnostic(test,test_base,bars,c) for c in SPEC['roundTripCostsPercent']]))
            latest_rows=rows if current and bars and current[-1]['date']==bars[-1]['date'] else next(r['rows'] for r in replay(current,lambda prefix:signal(rule['id'],prefix,indicator),calendar,events,days=1)['reports'] if r['days']==horizon)
            if latest_rows:
                latest=latest_rows[-1];forward.append(dict(id=rule['id'],name=rule['name'],days=horizon,bias=latest['bias'],score=latest['score'],asOf=latest['asOf'],model=f"候選研究 CR1 {rule['id']} {SPEC_HASH}-{ENGINE_HASH}"))
        reports.append(dict(days=horizon,winner=choose(results),candidates=results,v4Training=summary(train_base,train_base),v4Review=summary(test_base,test_base),trainingFrom=train_base[0]['asOf'] if train_base else None,trainingLastTarget=train_base[-1]['endDate'] if train_base else None,reviewFrom=cut,reviewThrough=bars[-1]['date'] if bars else None))
    input_hash=hashlib.sha256(json.dumps(dict(bars=bars,calendar=calendar,events=events),sort_keys=True,ensure_ascii=True).encode()).hexdigest()[:12]
    return dict(protocol=SPEC['id'],specHash=SPEC_HASH,engineHash=ENGINE_HASH,inputHash=input_hash,frozenAt=SPEC['frozenAt'],production='v4 unchanged',reports=reports,signals=forward,limitations=['前段訓練的到期日必須早於後段首日，避免跨界答案洩漏。','僅按訓練區挑選；後段90日已被檢視，結果是事後回顧，不是全新樣本外證據。','無訊號不預測，必須同時看覆蓋率；基準只比較相同發訊號窗口。','含成本診斷只做多，不放空；固定非重疊槽位、隔日開盤進及天期末收盤出。','0.2／0.5／1%為來回成本敏感度假設，不是實際稅費；回撤僅出場點。','研究標的由目前清單指定，未控制存活者偏誤；多組候選比較未作顯著性推論。','不自動替換v4；可全部淘汰，前瞻結果需封存後實際累積。'])
