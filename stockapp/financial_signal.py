"""Prospective-only FCF experiment; weights are policy, never backfit results."""
from datetime import date
from copy import deepcopy
import math

MODEL='透明規則 v5（技術80%／現金流20%試驗）；尚未經前瞻驗證'

def health_check(context):
    cash=context.get('cashFlow',{});quarters=cash.get('quarters',[])
    result=dict(version='fcf-health-v1',weight=.2,available=False,score=None,status='資料不足',current=None,previous=None,yearAgo=None,qoq=None,yoy=None,flags=[],historicalUseAllowed=False)
    if cash.get('status')=='not_applicable':result['status']='ETF不適用';return result
    if not quarters:return result
    rows=sorted(quarters,key=lambda r:r['periodEnd']);current=rows[-1]
    if (date.fromisoformat(context['asOf'])-date.fromisoformat(current['periodEnd'])).days>200:
        result['status']='財報過舊';return result
    year,q=map(int,current['period'].replace('-Q','-').split('-'))
    previous=next((r for r in rows if r['period']==f'{year if q>1 else year-1}-Q{q-1 if q>1 else 4}'),None)
    lastyear=next((r for r in rows if r['period']==f'{year-1}-Q{q}'),None)
    result.update(current=current,previous=previous,yearAgo=lastyear)
    if previous is None:result['status']='缺前一季同口徑資料';return result
    value,prior=current['FCF'],previous['FCF']
    if not all(type(v) in [int,float] and math.isfinite(v) for v in [value,prior,current['CFO'],previous['CFO']]):return result
    result['qoq']=(value-prior)/abs(prior)*100 if prior else None
    result['yoy']=(value-lastyear['FCF'])/abs(lastyear['FCF'])*100 if lastyear and lastyear['FCF'] else None
    if value<0:result['flags'].append('自由現金流為負')
    if value<0<=prior:result['flags'].append('由正／零轉負')
    if value<prior:result['flags'].append('較上季減少')
    if lastyear and value<lastyear['FCF']:result['flags'].append('較去年同期減少')
    if current['CFO']<previous['CFO']:result['flags'].append('營業現金流同步減少')
    if current['CFO']<0:result['flags'].append('營業現金流為負')
    if current['PPEcapex']>previous['PPEcapex']:result['flags'].append('設備資本支出增加，需查投資用途')
    level=100 if value>0 else 50 if value==0 else 0
    trend=100 if value>prior else 50 if value==prior else 0
    score=max(0,(level+trend)/2-(25 if current['CFO']<0 else 0))
    if cash.get('periodType')=='year_to_date' and cash.get('FCF') is not None and cash['FCF']<0:
        result['flags'].append('年度累計自由現金流仍為負，單季改善不能抵銷累計風險')
        score=min(score,50)
    result.update(available=True,score=score,status='風險偏高' if score<=25 else '需留意' if score<=50 else '現金流改善')
    result['definition']='健康分＝50%現金流正負＋50%季變化；營業現金流負值再扣25分，最低0；年度累計FCF為負時最高50分。非會計審計結論或勝率。'
    return result


def combine_signal(technical,context):
    h=context.get('health',{});result=dict(available=False,version='fcf-health-v1',technicalWeight=.8,financialWeight=.2,score=None,bias=None,technicalBias=technical.get('bias') if technical else None,reason=h.get('status','資料不足'))
    if not technical or not h.get('available'):return result
    score=round(.8*technical['score']+.2*h['score'],2)
    result.update(available=True,score=score,bias='偏多' if score>=65 else '偏空' if score<=35 else '震盪',reason='試驗規則：技術80%＋現金流健康20%；不代表已校準機率')
    return result
