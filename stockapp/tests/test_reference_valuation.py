import unittest
from datetime import datetime
from stockapp.server import normalize,TZ

class ValuationTests(unittest.TestCase):
    def test_older_close_only_reference_on_known_closed_day(self):
        cal=dict(years=[2026],closed={},opened={},unknown={})
        row=dict(c='2330',z='100',y='99',d='20261022',t='13:30:00')
        q=normalize(row,datetime(2026,10,24,13,tzinfo=TZ),cal)
        self.assertEqual(q['status'],'stale');self.assertTrue(q['valuationEligible'])
        self.assertEqual(q['expectedQuoteDate'],'2026-10-23')
        self.assertFalse(normalize(row,datetime(2026,10,23,10,tzinfo=TZ),cal)['valuationEligible'])
        row['t']='12:00:00'
        self.assertFalse(normalize(row,datetime(2026,10,24,13,tzinfo=TZ),cal)['valuationEligible'])
    def test_no_unknown_calendar_future_or_older_than_seven_days(self):
        row=dict(c='2330',z='100',y='99',d='20261015',t='13:30:00')
        cal=dict(years=[2026],closed={},opened={},unknown={})
        for c in [cal,{},None]:
            self.assertFalse(normalize(row,datetime(2026,10,24,13,tzinfo=TZ),c)['valuationEligible'])
        row['d']='20261026'
        self.assertFalse(normalize(row,datetime(2026,10,24,13,tzinfo=TZ),cal)['valuationEligible'])
