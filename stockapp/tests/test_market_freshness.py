import unittest
from datetime import datetime
from stockapp.server import market_data_needs_refresh,TZ

class MarketFreshnessTests(unittest.TestCase):
    def test_recent_snapshot_still_needs_today_coverage_after_close(self):
        actions=dict(fetchedAt='2026-10-26T22:55:00+08:00',historyTo='2026-10-26',otcHistoryTo='2026-10-26')
        cal=dict(years=[2026],closed={'2026-10-26':'holiday'},opened={},unknown={})
        self.assertTrue(market_data_needs_refresh(actions,cal,datetime(2026,10,27,22,0,tzinfo=TZ)))
        actions.update(historyTo='2026-10-27',otcHistoryTo='2026-10-27')
        self.assertFalse(market_data_needs_refresh(actions,cal,datetime(2026,10,27,22,0,tzinfo=TZ)))
        actions['otcHistoryTo']='2026-10-26'
        self.assertTrue(market_data_needs_refresh(actions,cal,datetime(2026,10,27,22,0,tzinfo=TZ)))
    def test_preopen_accepts_previous_completed_session(self):
        actions=dict(fetchedAt='2026-10-26T22:55:00+08:00',historyTo='2026-10-22',otcHistoryTo='2026-10-22')
        cal=dict(years=[2026],closed={'2026-10-23':'holiday','2026-10-26':'holiday'},opened={},unknown={})
        self.assertFalse(market_data_needs_refresh(actions,cal,datetime(2026,10,27,8,0,tzinfo=TZ)))
