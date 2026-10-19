"""Partial ex-right adjustment from official reference/previous-close ratios."""
import json, math
from pathlib import Path
FILE=Path(__file__).with_name('corporate-actions.json')

def snapshot():
    try:
        d=json.loads(FILE.read_text(encoding='utf-8'))
        if d.get('version')!=1:return {}
        return d
    except (OSError,ValueError):return {}

def adjust(bars,events):
    result=[dict(b) for b in bars];applied=[];unresolved=[]
    if not bars:return result,applied,unresolved
    unique={}
    for e in events:
        if not bars[0]['date']<e['date']<=bars[-1]['date']:continue
        if e.get('manualReview'):unresolved.append(e);continue
        previous=e.get('previousClose');reference=e.get('referencePrice')
        if not isinstance(previous,(int,float)) or not isinstance(reference,(int,float)) or previous<=0 or reference<=0:unresolved.append(e);continue
        ratio=reference/previous
        if not math.isfinite(ratio) or not 0<ratio<(1000 if e.get('kind') in ['ETF分割／反分割','變更面額'] else 5):unresolved.append(e);continue
        if e['date'] in unique and abs(unique[e['date']]['factor']-ratio)>1e-7:unresolved.append(e);continue
        unique[e['date']]={**e,'factor':ratio}
    if unresolved:return result,[],unresolved
    for date,e in sorted(unique.items()):
        # Require a matching original anchor; never infer it from ex-day market moves.
        anchor=next((b for b in reversed(bars) if b['date']<date),None)
        if not anchor or abs(anchor['close']/e['previousClose']-1)>.005:unresolved.append(e);continue
        for b in result:
            if b['date']<date:
                for key in ['open','high','low','close']:b[key]*=e['factor']
        applied.append(e)
    if unresolved:return [dict(b) for b in bars],[],unresolved
    return result,applied,[]

def for_stock(sid,exchange):
    d=snapshot();events=[e for e in d.get('events',[]) if e['id']==sid and e['exchange']==exchange]
    return events,dict(fetchedAt=d.get('fetchedAt'),sources=d.get('sources',[]),errors=d.get('errors',[]),historyFrom=d.get('historyFrom'),historyTo=d.get('historyTo'),coverage='上市除權息、ETF分割及面額變更歷史；減資僅標記待核對；上櫃僅近期快照')
