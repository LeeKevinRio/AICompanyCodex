import unittest
from stockapp.strategy_validation import validate
from stockapp.tests.test_analysis import bars as dated_bars,CAL

def bars(n):return [dict(b,open=100,high=102,low=99,close=101) for b in dated_bars(n)]

class ValidationTests(unittest.TestCase):
    def test_flat_no_trade_and_costed_same_window_baseline(self):
        r=validate(bars(200),lambda b:dict(bias='震盪'),calendar=CAL)
        for h in r['reports']:
            self.assertEqual(h['tradeCount'],0);self.assertEqual(h['netReturn'],0)
            self.assertIsNone(h['winRate']);self.assertGreater(h['windowCount'],0)
    def test_next_open_entry_and_only_available_prefix(self):
        seen=[]
        def signal(prefix):seen.append(len(prefix));return dict(bias='偏多')
        b=bars(200);r=validate(b,signal,calendar=CAL)
        self.assertEqual(min(seen),60)
        for h in r['reports']:
            for t in h['trades']:
                self.assertGreater(t['entryDate'],t['signalDate'])
                self.assertAlmostEqual(t['netReturn'],.5)
            self.assertAlmostEqual(h['netReturn'],h['alwaysEnterReturn'])
    def test_event_windows_excluded_and_invalid_cost_rejected(self):
        b=bars(200);r=validate(b,lambda b:dict(bias='偏多'),[dict(date=b[160]['date'])],calendar=CAL)
        self.assertTrue(any(h['excludedWindows'] for h in r['reports']))
        with self.assertRaises(ValueError):validate(b,lambda b:None,cost_percent=-1)
