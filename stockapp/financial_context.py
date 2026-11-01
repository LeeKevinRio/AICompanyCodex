"""Public financial evidence overlay; never an input to historical predictions.

The reviewed IR snapshot is intentionally explicit rather than an invented
universal cash-flow API. Unknown amounts remain None, never zero.
"""
from copy import deepcopy
from datetime import date, datetime
import math
from urllib.parse import urlencode

IR = 'https://investor.tsmc.com/english/quarterly-results/2026/q3'
FS = 'https://investor.tsmc.com/english/encrypt/files/encrypt_file/reports/2026-10/3a94d1034b9e6b22446b674f7aaf3d088a12a193/FS.pdf'
REPORT = 'https://investor.tsmc.com/english/encrypt/files/encrypt_file/reports/2026-10/f83780000ddc0c3b48e57a87eab6814c4ab35058/3Q26%20ManagementReport.pdf'


def parse_cashflows(payload, sid, as_of, source):
    """FinMind values are NTD units, year-to-date, not individual quarters."""
    if not isinstance(payload, dict) or payload.get('status') != 200:
        return None
    rows = [r for r in payload.get('data', []) if str(r.get('stock_id')) == str(sid)
            and str(r.get('date', '')) <= as_of]
    if not rows:
        return None
    period = max(r['date'] for r in rows)
    values = {}
    for row in rows:
        if row['date'] != period:
            continue
        try:
            number = float(row['value'])
            if math.isfinite(number):
                values[row['type']] = number
        except (ValueError, TypeError, KeyError):
            pass
    # These are net operating cash, not the pre-interest/tax subtotal
    # CashReceivedThroughOperations or CashProvidedByOperatingActivities.
    cfo = values.get('CashFlowsFromOperatingActivities', values.get('NetCashInflowFromOperatingActivities'))
    signed_ppe = values.get('PropertyAndPlantAndEquipment')
    capex = -signed_ppe if signed_ppe is not None and signed_ppe <= 0 else None
    if cfo is None or capex is None:
        return None
    return dict(status='available', CFO=cfo, PPEcapex=capex, FCF=cfo-capex,
        intangibleCapex=None, reportedFCF=None, period=period, periodType='year_to_date',
        periodStart=period[:4]+'-01-01', unit='NTD', publishedAt=None,
        source=source, sourceType='third_party_aggregator', provider='FinMind',
        definition='FCF = 累計營業活動淨現金流 − 累計取得不動產、廠房及設備支出；不含未知無形資產支出',
        reason=None, historicalUseAllowed=False,
        publicationNote='date為財報期末，不是公告日期；不可用於歷史回測',
        documentation='https://finmind.github.io/tutor/TaiwanMarket/Fundamental/')


def _forecast_achievement(sid, exchange, fetch_json):
    """Do not turn report snapshot dates into forecast publication dates."""
    url = ('https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap15_O' if exchange == 'otc'
           else 'https://openapi.twse.com.tw/v1/opendata/t187ap15_L')
    try:
        payload = fetch_json(url, ttl=21600)
        rows = payload if isinstance(payload, list) else []
        return [dict(type='company_forecast_achievement', source=url,
            publishedAt=None, snapshotDate=row.get('出表日期'),
            period=dict(year=row.get('年度'), quarter=row.get('季別'), covered=row.get('涵蓋期間')),
            forecastRangeRaw=row.get('截至該季綜合損益預測數'),
            actualRaw=row.get('截至該季經會計師查核或核閱數'), unit=None,
            note='官方簡式財測達成表，非完整guidance；出表日期非原始公告日，單位未核實')
            for row in rows if str(row.get('公司代號')) == str(sid)]
    except Exception:
        return []


def _day(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return date.fromisoformat(str(value)[:10]).isoformat()


def build_context(sid, exchange, fetch_json=None, as_of=None):
    """Return dated public evidence, without changing a directional signal.

    fetch_json loads the labelled FinMind aggregator and official forecast table.
    TWSE t187ap06 is
    income statements, not cash flow; t187ap15 is forecast achievement, not
    a complete guidance feed. Neither is mislabelled as free cash flow here.
    This module must not be called by walk-forward or historical evaluation.
    """
    as_of = _day(as_of or date.today())
    cash = dict(status='unavailable', CFO=None, PPEcapex=None, FCF=None,
                intangibleCapex=None, reportedFCF=None, period=None, unit=None,
                publishedAt=None, source=None,
                definition='FCF = 營業現金流 − 取得不動產、廠房及設備支出；不含未披露無形資產支出',
                reason='尚未接入可核實的該公司現金流來源；不代表公司未公告')
    result = dict(asOf=as_of, cashFlow=cash, guidance=[],
                  historicalUseAllowed=False, directionOverride=None,
                  sourceMode='reviewed_official_snapshot',
                  verifiedAt='2026-11-01',
                  strategy=dict(directionOverride=None, warnings=[],
                                note='財務背景僅供風險與分歧檢查，不改變3／5日方向或命中率'))
    result['forecastAchievement'] = []
    if str(sid).startswith('00'):
        cash.update(status='not_applicable', definition='ETF不適用發行公司營業現金流與公司財測',
                    reason='ETF應查基金淨值、追蹤誤差、費用及成分風險，不能套用公司FCF',
                    provider='不適用')
        result['sourceMode'] = 'not_applicable'
        result['strategy']['note'] = cash['reason']
        return result
    if fetch_json is not None:
        result['forecastAchievement'] = _forecast_achievement(sid, exchange, fetch_json)
        url = 'https://api.finmindtrade.com/api/v4/data?'+urlencode(dict(
            dataset='TaiwanStockCashFlowsStatement', data_id=str(sid),
            start_date=str(int(as_of[:4])-2)+'-01-01', end_date=as_of))
        try:
            parsed = parse_cashflows(fetch_json(url, ttl=21600), sid, as_of, url)
            if parsed:
                result['cashFlow'] = parsed
                result['sourceMode'] = 'third_party_aggregator'
                if parsed['FCF'] < 0:
                    result['strategy']['warnings'].append('累計FCF為負，需查資本支出與營運週期；不直接判定短線偏空')
        except Exception:
            result['strategy']['warnings'].append('現金流來源暫時無法取得，保留未知')
    if str(sid) != '2330' or exchange not in ('tse', 'TWSE'):
        result['strategy']['warnings'].append('公司IR財測尚未完整接入；財務背景不計入方向分數')
        return result
    if as_of < '2026-10-15':
        cash['reason'] = '此官方快照發布日晚於指定日期，不提供未發布資訊'
        return result
    cash.update(status='available', CFO=919776, PPEcapex=443206, FCF=476570,
                reportedFCF=476560, period='2026-Q3', periodType='quarter',
                unit='NTD million', publishedAt='2026-10-15', source=FS,
                sourceType='official_company_ir', provider='TSMC',
                reportedFCFSource=REPORT, sourcePage=4, unaudited=True,
                reason=None,
                precisionNote='衍生FCF依財報百萬元數字計算；公司報告FCF為476.56十億元，分開保存，不強制相等',
                intangibleNote='簡明報表未單列無形資產取得，未知不視為零')
    result['cashFlow'] = cash
    result['sourceMode'] = 'reviewed_official_snapshot'
    for metric, low, high, unit in (
            ('revenue', 52.3, 54.3, 'USD billion'),
            ('grossMargin', 65.0, 67.0, '%'),
            ('operatingMargin', 56.5, 58.5, '%')):
        result['guidance'].append(dict(type='company_guidance', metric=metric,
            low=low, high=high, unit=unit, period='2026-Q4',
            publishedAt='2026-10-15', source=IR,
            note='公司展望，非券商預估，亦非已實現績效'))
    result['strategy']['warnings'].append('正現金流不等於短線必漲；財測需以後續公司公告核對')
    if as_of > '2027-01-15':
        cash['status'] = 'stale'
        result['strategy']['warnings'].append('人工核實快照可能過期，需更新官方公告')
    return deepcopy(result)
