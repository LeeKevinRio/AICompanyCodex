import unittest
from datetime import datetime
from unittest.mock import patch
from stockapp.server import normalize, TZ, number, fetch_quotes, CACHE
class QuoteTests(unittest.TestCase):
    def test_missing_trade_never_uses_bid_or_previous(self):
        q=normalize({'c':'2330','z':'-','y':'100','b':'101_','d':'20261013','t':'10:00:00'},datetime(2026,10,13,10,0,tzinfo=TZ))
        self.assertIsNone(q['price']);self.assertEqual(q['status'],'no_trade')
    def test_session_and_stale(self):
        row={'c':'2330','z':'105','y':'100','d':'20261013','t':'10:00:00'}
        self.assertEqual(normalize(row,datetime(2026,10,13,10,1,tzinfo=TZ))['status'],'active')
        self.assertEqual(normalize(row,datetime(2026,10,13,10,5,tzinfo=TZ))['status'],'stale')
        self.assertEqual(normalize(row,datetime(2026,10,13,15,0,tzinfo=TZ))['status'],'last_trade')
        self.assertEqual(normalize(row,datetime(2026,10,14,10,0,tzinfo=TZ))['status'],'stale')
    def test_volume_total_lots_to_shares(self):
        self.assertEqual(normalize({"v":"23129"})["volumeShares"],23129000)
        self.assertEqual(normalize({"v":"0"})["volumeShares"],0)
        for v in ["-","nan","inf","-1"]:self.assertIsNone(normalize({"v":v})["volumeShares"])
    def test_premarket_and_weekend_close_reference(self):
        row={"c":"2330","z":"100","y":"99","d":"20261014","t":"13:30:00"}
        self.assertEqual(normalize(row,datetime(2026,10,15,8,0,tzinfo=TZ))["status"],"previous_close")
        self.assertEqual(normalize(row,datetime(2026,10,15,10,0,tzinfo=TZ))["status"],"stale")
        row["d"]="20261016"
        self.assertEqual(normalize(row,datetime(2026,10,18,12,0,tzinfo=TZ))["status"],"previous_close")
        row["t"]="12:00:00"
        self.assertEqual(normalize(row,datetime(2026,10,18,12,0,tzinfo=TZ))["status"],"stale")
    def test_bad_numbers(self):
        for v in ['-', 'nan','inf',0,-1]:self.assertIsNone(number(v))
    def test_upstream_failure_is_not_fake_data(self):
        CACHE.clear()
        with patch('stockapp.server.urllib.request.urlopen',side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):fetch_quotes(['2330'])
if __name__=='__main__':unittest.main()
