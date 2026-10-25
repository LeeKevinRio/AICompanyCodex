import unittest
from stockapp.update_market_data import parse_otc_history,merge_action_snapshot

def payload():return dict(stat='ok',date='20250901~20261025',tables=[dict(fields=['除權息日期','代號','名稱','除權息前收盤價','除權息參考價'],totalCount=1,data=[['114/09/01','4138','公司','100','95',0,5,5,'除息']])])

class OTCHistoryTests(unittest.TestCase):
    def test_parse_verified_range_schema_count(self):
        rows=parse_otc_history(payload(),'official','2025-09-01','2026-10-25')
        self.assertEqual(rows[0]['exchange'],'otc');self.assertEqual(rows[0]['referencePrice'],95)
    def test_default_wrong_dates_and_truncated_pages_rejected(self):
        p=payload();p['date']='20261025~20261027'
        with self.assertRaises(ValueError):parse_otc_history(p,'official','2025-09-01','2026-10-25')
        p=payload();p['tables'][0]['totalCount']=2
        with self.assertRaises(ValueError):parse_otc_history(p,'official','2025-09-01','2026-10-25')
    def test_failed_source_keeps_history_coverage(self):
        old=dict(events=[],otcHistoryFrom='2025-09-01',otcHistoryTo='2026-10-22')
        r=merge_action_snapshot(old,dict(events=[],sources=[]),['https://www.tpex.org.tw/www/zh-tw/bulletin/exDailyQ?new'],'now')
        self.assertEqual(r['otcHistoryTo'],'2026-10-22')
