import unittest
from stockapp.update_market_data import parse_reference_table
from stockapp.corporate_actions import adjust

class ReferenceTests(unittest.TestCase):
    def test_official_split_schema_and_prices(self):
        d=dict(stat='OK',fields=['恢復買賣日期','ETF代號','名稱','分割','停止買賣前收盤價格','恢復買賣參考價'],data=[['115/07/01','00685L','基金','分割','100','10']])
        e=parse_reference_table(d,'official','ETF分割／反分割')[0]
        self.assertEqual(e['date'],'2026-07-01');self.assertEqual(e['referencePrice'],10)
        d['fields'][4]='未確認欄位'
        with self.assertRaises(ValueError):parse_reference_table(d,'official','ETF分割／反分割')
    def test_reverse_split_supports_large_documented_ratio_with_anchor(self):
        bars=[dict(date='2026-06-30',open=2,high=2,low=2,close=2,volume=100),dict(date='2026-07-01',open=20,high=20,low=20,close=20,volume=10)]
        e=dict(date='2026-07-01',kind='ETF分割／反分割',previousClose=2,referencePrice=20)
        result,applied,unresolved=adjust(bars,[e])
        self.assertEqual(result[0]['close'],20);self.assertEqual(result[0]['volume'],100)
        self.assertEqual(len(applied),1);self.assertFalse(unresolved);self.assertEqual(bars[0]['close'],2)
        e['previousClose']=3
        self.assertTrue(adjust(bars,[e])[2])
    def test_reduction_is_manual_not_automatic_return_adjustment(self):
        d=dict(stat='OK',fields=['恢復買賣日期','股票代號','名稱','停止買賣前收盤價格','恢復買賣參考價'],data=[['115/07/01','2025','公司','10','20']])
        e=parse_reference_table(d,'official','減資恢復交易')[0]
        bars=[dict(date='2026-06-30',close=10),dict(date='2026-07-01',close=20)]
        result,applied,unresolved=adjust(bars,[e])
        self.assertEqual(result,bars);self.assertFalse(applied);self.assertEqual(len(unresolved),1)
