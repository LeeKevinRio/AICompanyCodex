import unittest
from datetime import datetime,timezone
from copy import deepcopy
from stockapp.us_market import parse_chart,TICKER

class USQuoteTests(unittest.TestCase):
    def fixture(self):
        stamps=[int(datetime(2026,10,d,20,tzinfo=timezone.utc).timestamp()) for d in [28,29,30]]
        return {'chart':{'result':[{'meta':dict(symbol='AAPL',currency='USD',exchangeName='NMS',instrumentType='EQUITY',regularMarketPrice=103,regularMarketTime=stamps[-1],chartPreviousClose=50), 'timestamp':stamps,'indicators':{'quote':[{'close':[100,102,103],'volume':[10,20,30]}]}}]}}
    def test_previous_day_not_six_month_chart_anchor(self):
        q=parse_chart(self.fixture(),'AAPL',datetime(2026,11,1,tzinfo=timezone.utc))
        self.assertEqual(q['previous'],102)
        self.assertAlmostEqual(q['change'],100/102)
        self.assertFalse(q['forecastEnabled'])
        self.assertEqual(q['marketDate'],'2026-10-30')
    def test_reject_future_stale_other_currency_or_wrong_identity(self):
        for field,value in [('currency','TWD'),('symbol','MSFT'),('exchangeName','TAI'),('regularMarketPrice',float('nan')),('regularMarketTime',9999999999)]:
            p=self.fixture();p['chart']['result'][0]['meta'][field]=value
            with self.assertRaises(ValueError):parse_chart(p,'AAPL',datetime(2026,11,1,tzinfo=timezone.utc))
        with self.assertRaises(ValueError):parse_chart(self.fixture(),'AAPL',datetime(2026,12,1,tzinfo=timezone.utc))
    def test_ticker_disallows_paths_and_query_injection(self):
        self.assertTrue(TICKER.fullmatch('BRK-B'))
        for symbol in ['../AAPL','AAPL?x=1','2330.TW','AAPL/USD','']:
            self.assertFalse(TICKER.fullmatch(symbol))
