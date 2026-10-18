import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from stockapp.analysis import indicators, forecast, parse_bars, numeric, roc_date, TZ, analyze, RESULT_CACHE

def bars(n=240,step=.5):
    return [dict(date=f'2026-{i//28+1:02d}-{i%28+1:02d}',open=100+i*step,high=102+i*step,low=98+i*step,close=100+i*step,volume=10000,note='') for i in range(n)]

class AnalysisTests(unittest.TestCase):
    def test_numeric_and_roc_dates(self):
        self.assertEqual(numeric('1,234.50'),1234.5)
        self.assertEqual(numeric('-3.5'),-3.5)
        self.assertIsNone(numeric('nan'))
        self.assertEqual(roc_date('115/10/13'),'2026-10-13')
        self.assertEqual(roc_date('1151013'),'2026-10-13')
    def test_exchange_volume_units_and_bad_close(self):
        row=['115/10/13','1,000','0','100','105','99','103']
        self.assertEqual(parse_bars({'data':[row]},'tse')[0]['volume'],1000)
        payload={'tables':[{'fields':['日期','成交張數'],'data':[row]}]}
        self.assertEqual(parse_bars(payload,'otc')[0]['volume'],1000000)
        row[6]='--'
        self.assertEqual(parse_bars(payload,'otc'),[])
    def test_indicator_values_not_only_score(self):
        a=indicators(bars(80,0))
        self.assertEqual(a['rsi'],50)
        self.assertEqual(a['atr'],4)
        self.assertEqual(a['ma']['20'],100)
        self.assertEqual(a['volumeRatio'],1)
        self.assertAlmostEqual(a['macd'],0)
        rising=indicators(bars(80))
        self.assertEqual(rising['rsi'],100)
        self.assertEqual(rising['ma']['5'],138.5)
        self.assertIsNone(indicators(bars(59)))
    def test_forecasts_use_only_past_features(self):
        b=bars();current=indicators(b);lengths=[]
        actual=indicators
        def spy(prefix):
            lengths.append(len(prefix));return actual(prefix)
        with patch('stockapp.analysis.indicators',side_effect=spy):result=forecast(b,current)
        expected=list(range(60,len(b)-3+1,3))+list(range(60,len(b)-5+1,5))
        self.assertEqual(lengths,expected)
        self.assertEqual([f['days'] for f in result],[3,5])
        for f in result:self.assertIsNone(f['probability'])
    def test_small_samples_never_claim_probability_or_hit_rate(self):
        b=bars(70);result=forecast(b,indicators(b))
        for f in result:
            self.assertEqual(f['evidence'],'同類樣本過少')
            self.assertIsNone(f['reviewHitRate'])
            self.assertIsNone(f['probability'])
            self.assertIsNone(f['lowReturn'])
    def test_26_samples_show_descriptive_range_without_probability(self):
        b=bars(190)
        result=forecast(b,indicators(b))
        five=result[1]
        self.assertEqual(five['sampleCount'],26)
        self.assertEqual(five['evidence'],'初步歷史區間')
        self.assertIsNotNone(five['lowReturn'])
        self.assertLessEqual(five['lowReturn'],five['medianReturn'])
        self.assertLessEqual(five['medianReturn'],five['highReturn'])
        self.assertIsNone(five['probability'])
        self.assertIsNone(five['reviewHitRate'])
    def test_down_volume_spike_reduces_short_term_score(self):
        b=bars(80);ordinary=indicators(b);b[-1]['close']=b[-2]['close']-1;b[-1]['volume']=30000
        a=indicators(b)
        self.assertLess(a['score'],ordinary['score'])
        self.assertTrue(any('放量下跌' in r for r in a['reasons']))
    def test_partial_history_and_event_risk_disable_plan(self):
        b=bars(90)
        today=datetime.now(TZ).date()
        for i,row in enumerate(b):row['date']=(today-timedelta(days=89-i)).isoformat()
        for failed,event in [(1,False),(0,True)]:
            RESULT_CACHE.clear()
            f={'announcements':[{'riskFlag':True}] if event else [],'score':None}
            with patch('stockapp.analysis.history',return_value=(b,[],failed)),patch('stockapp.analysis.fundamentals',return_value=f):a=analyze('9999','tse')
            self.assertFalse(a['planEnabled'])
            self.assertEqual(a['forecasts'],[])
    def test_recent_split_never_reuses_old_price_scale(self):
        b=bars(90)
        today=datetime.now(TZ).date()
        for i,row in enumerate(b):
            row['date']=(today-timedelta(days=89-i)).isoformat()
            if i>=60:
                for key in ['open','high','low','close']:row[key]/=10
        RESULT_CACHE.clear()
        with patch('stockapp.analysis.history',return_value=(b,[],0)),patch('stockapp.analysis.fundamentals',return_value={'announcements':[]}):a=analyze('9999','tse')
        self.assertEqual(a['historyCount'],30)
        self.assertIsNone(a['technical'])
        self.assertFalse(a['planEnabled'])
if __name__=='__main__':unittest.main()
