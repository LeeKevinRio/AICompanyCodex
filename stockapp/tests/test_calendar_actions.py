import unittest
from datetime import datetime,date,timedelta
from unittest.mock import patch
from stockapp.market_calendar import parse_schedule,is_session,previous_session,next_sessions,TZ,iso_date,merge_schedules
from stockapp.server import normalize
from stockapp.corporate_actions import adjust
from stockapp.analysis import analyze,RESULT_CACHE

def calendar():
    rows=[dict(Date='1150102',Name='開始交易日',Description='開始交易')]
    rows += [dict(Date=f'11502{d:02d}',Name='市場無交易' if d<14 else '春節',Description='' if d<14 else '放假') for d in [12,13,16,17,18,19,20]]
    rows += [dict(Date='1151026',Name='紀念日',Description='補假')]
    return parse_schedule(rows)

class CalendarTests(unittest.TestCase):
    def test_holidays_and_settlement_days(self):
        c=calendar()
        self.assertFalse(is_session(date(2026,2,12),c))
        self.assertEqual(previous_session(date(2026,2,23),c),date(2026,2,11))
        self.assertTrue(is_session(date(2026,1,2),c))
        self.assertEqual(next_sessions(date(2026,10,23),3,c),['2026-10-27','2026-10-28','2026-10-29'])
    def test_merge_preserves_past_year_but_replaces_revised_current_year(self):
        old=calendar();new=dict(years=[2027],closed={"2027-01-01":"假日"},opened={},unknown={})
        both=merge_schedules(old,new);self.assertEqual(both["years"],[2026,2027]);self.assertIn("2026-10-26",both["closed"])
        revised=dict(years=[2026],closed={"2026-01-01":"假日"},opened={},unknown={})
        self.assertNotIn("2026-10-26",merge_schedules(old,revised)["closed"])
    def test_unknown_year_not_guessed(self):
        c=calendar();self.assertIsNone(is_session(date(2027,1,4),c));self.assertIsNone(next_sessions(date(2026,12,31),1,c))
        self.assertEqual(iso_date('115年10月26日'),'2026-10-26');self.assertIsNone(iso_date('1150230'))
    def test_holiday_quote_reference_not_intraday(self):
        row=dict(c='2330',z='100',y='99',d='20261023',t='13:30:00')
        self.assertEqual(normalize(row,datetime(2026,10,26,10,tzinfo=TZ),calendar())['status'],'previous_close')
        self.assertEqual(normalize(row,datetime(2026,10,27,10,tzinfo=TZ),calendar())['status'],'stale')
        row['d']='20261026'
        self.assertEqual(normalize(row,datetime(2026,10,26,10,tzinfo=TZ),calendar())['status'],'calendar_conflict')

def bar(day,price):return dict(date=day,open=price,high=price,low=price,close=price,volume=1000,note='')
class ActionTests(unittest.TestCase):
    def test_cash_ratio_removes_mechanical_gap_without_changing_raw(self):
        raw=[bar('2026-10-08',100),bar('2026-10-09',98)]
        result,events,bad=adjust(raw,[dict(date='2026-10-09',previousClose=100,referencePrice=98)])
        self.assertEqual(result[0]['close'],98);self.assertEqual(result[-1]['close'],98)
        self.assertEqual(raw[0]['close'],100);self.assertEqual(result[0]['volume'],1000);self.assertEqual(len(events),1);self.assertFalse(bad)
    def test_multiple_ratios_and_future_events(self):
        raw=[bar('2026-10-08',100),bar('2026-10-09',98),bar('2026-10-14',100),bar('2026-10-15',99)]
        events=[dict(date='2026-10-09',previousClose=100,referencePrice=98),dict(date='2026-10-15',previousClose=100,referencePrice=99),dict(date='2026-10-20',previousClose=100,referencePrice=50)]
        result,used,bad=adjust(raw,events)
        self.assertAlmostEqual(result[0]['close'],97.02);self.assertAlmostEqual(result[1]['close'],97.02);self.assertEqual(result[-1]['close'],99);self.assertEqual(len(used),2);self.assertFalse(bad)
    def test_conflict_missing_or_wrong_anchor_never_partially_adjust(self):
        raw=[bar('2026-10-08',100),bar('2026-10-09',98)]
        for events in [[dict(date='2026-10-09',previousClose=200,referencePrice=98)],[dict(date='2026-10-09',previousClose=100,referencePrice=None)],[dict(date='2026-10-09',previousClose=100,referencePrice=98),dict(date='2026-10-09',previousClose=100,referencePrice=97)]]:
            result,used,bad=adjust(raw,events);self.assertEqual(result,raw);self.assertFalse(used);self.assertTrue(bad)

class PipelineTests(unittest.TestCase):
    def test_upcoming_event_and_unknown_calendar_disable_only_valid_pipeline(self):
        today=datetime.now(TZ).date();dates=[];d=today
        while len(dates)<75:
            if d.weekday()<5:dates.append(d)
            d-=timedelta(days=1)
        dates.reverse();raw=[bar(d.isoformat(),100+i*.1) for i,d in enumerate(dates)]
        c=dict(years=[today.year],closed={},opened={},unknown={})
        meta=dict(fetchedAt=datetime.now(TZ).isoformat(),coverage='test',historyFrom=dates[0].isoformat(),historyTo=today.isoformat())
        next_date=next_sessions(dates[-1],1,c)[0]
        for events,cal,expected in [([],c,True),([dict(id='9999',exchange='tse',date=next_date,kind='息')],c,False),([],None,False)]:
            RESULT_CACHE.clear()
            with patch('stockapp.analysis.history',return_value=(raw,[],0)),patch('stockapp.analysis.fundamentals',return_value={'announcements':[]}),patch('stockapp.analysis.for_stock',return_value=(events,meta)),patch('stockapp.analysis.load_calendar',return_value=cal):result=analyze('9999','tse')
            self.assertEqual(result['planEnabled'],expected)
            if not expected:self.assertEqual(result['forecasts'],[])

if __name__=='__main__':unittest.main()
