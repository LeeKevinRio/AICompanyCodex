import unittest
from copy import deepcopy
from unittest.mock import patch
from stockapp.analysis import forecast,indicators
from stockapp.strategy_validation import validate
from stockapp.historical_evaluation import observations
from stockapp.tests.test_analysis import bars,CAL


class StrictEvaluationTests(unittest.TestCase):
    def test_forecast_missing_scheduled_day_is_excluded_not_extended(self):
        b=bars(70,0);original=forecast(b,indicators(b),CAL)[0]
        missing=b.pop(60)['date'];result=forecast(b,indicators(b),CAL)[0]
        self.assertEqual(original['reviewCount'],3)
        self.assertEqual(result['reviewCount'],2)
        self.assertEqual(result['reviewExcludedCount'],1)
        first=observations(b,indicators,CAL)[0]['rows'][0]
        self.assertEqual(first['status'],'缺指定日線')
        self.assertLess(missing,first['endDate'])
        self.assertEqual(first['endDate'],bars(70,0)[62]['date'])

    def test_forecast_event_window_excluded_like_real_journal(self):
        b=bars(70,0)
        event=dict(date=b[60]['date'],previousClose=100,referencePrice=100)
        r=forecast(b,indicators(b),CAL,[event])[0]
        self.assertEqual(r['reviewCount'],2)
        self.assertEqual(r['reviewExcludedCount'],1)

    def test_trade_entry_missing_does_not_move_to_next_available_open(self):
        b=bars(200,0);split=60+int((len(b)-60)*.7)
        anchor=b[split]['date'];removed=b.pop(split+1)['date']
        r=validate(b,lambda prefix:dict(bias='偏多'),calendar=CAL)
        three=r['reports'][0]
        self.assertGreaterEqual(three['excludedWindows'],1)
        self.assertFalse(any(t['signalDate']==anchor for t in three['trades']))
        self.assertFalse(any(t['entryDate']==removed for t in three['trades']))

    def test_future_event_cannot_change_earlier_prefix_used_for_features(self):
        b=bars(160,0);event=dict(date=b[140]['date'],previousClose=100,referencePrice=50)
        for row in b[140:]:
            for key in ['open','high','low','close']:row[key]/=2
        seen=[]
        def spy(prefix):
            if prefix[-1]['date']==b[139]['date']:seen.append(deepcopy(prefix))
            return indicators(prefix)
        with patch('stockapp.analysis.indicators',side_effect=spy):
            forecast(b,indicators(b),CAL,[event])
        validate(b,spy,[event],calendar=CAL)
        self.assertEqual(len(seen),2)
        for prefix in seen:
            self.assertEqual(prefix[0]['close'],100)
            self.assertEqual(prefix[-1]['close'],100)

    def test_unknown_calendar_never_guesses_forecast_or_trade_outcome(self):
        b=bars(200,0);unknown=dict(years=[],closed={},opened={},unknown={})
        for r in forecast(b,indicators(b),unknown):
            self.assertEqual(r['reviewCount'],0)
            self.assertIsNone(r['medianReturn'])
        for r in validate(b,lambda p:dict(bias='偏多'),calendar=unknown)['reports']:
            self.assertEqual(r['windowCount'],0)
            self.assertEqual(r['tradeCount'],0)
