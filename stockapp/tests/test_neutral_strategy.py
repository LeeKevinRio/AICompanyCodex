import unittest
from stockapp.analysis import indicators,forecast,compare_signal

def bars(prices):
    return [dict(date=f'day-{i:03}',open=p,high=p+1,low=p-1,close=p,volume=10000) for i,p in enumerate(prices)]

class NeutralStrategyTests(unittest.TestCase):
    def test_flat_neutral_including_three_and_five_day_forecasts(self):
        b=bars([100]*240);t=indicators(b)
        self.assertEqual(t['score'],50);self.assertEqual(t['bias'],'震盪')
        self.assertTrue(all('等於' in r for r in t['reasons']))
        for f in forecast(b,t):
            self.assertEqual(f['bias'],'震盪');self.assertEqual(f['medianReturn'],0)
            self.assertEqual(f['lowReturn'],0);self.assertEqual(f['highReturn'],0)
    def test_tiny_float_noise_does_not_turn_neutral_into_bearish(self):
        t=indicators(bars([100+(i%2)*1e-10 for i in range(120)]))
        self.assertEqual(t['score'],50);self.assertEqual(t['bias'],'震盪')
    def test_rising_falling_and_missing_volume(self):
        self.assertEqual(indicators(bars([100+i*.5 for i in range(120)]))['bias'],'偏多')
        self.assertEqual(indicators(bars([200-i*.5 for i in range(120)]))['bias'],'偏空')
        b=bars([100]*120)
        for x in b:x['volume']=None
        t=indicators(b);self.assertEqual(t['score'],50);self.assertIsNone(t['volumeRatio'])
    def test_sign_tolerance_symmetric_and_not_a_large_deadzone(self):
        self.assertEqual(compare_signal(100,100),0)
        self.assertEqual(compare_signal(100.01,100),1)
        self.assertEqual(compare_signal(100,100.01),-1)
