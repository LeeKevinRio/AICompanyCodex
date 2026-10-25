import unittest
from datetime import date,timedelta
from copy import deepcopy
from stockapp.analysis import indicators
from stockapp.walk_forward import replay

def bars():
    result=[];day=date(2026,1,2)
    while len(result)<160:
        if day.weekday()<5:
            p=100+len(result)*.1
            result.append(dict(date=day.isoformat(),open=p,high=p+1,low=p-1,close=p,volume=10000))
        day+=timedelta(days=1)
    return result
CAL=dict(years=[2026],closed={},opened={},unknown={})

class ReplayTests(unittest.TestCase):
    def test_thirty_daily_anchors_and_exact_three_five_pending(self):
        b=bars();seen=[]
        def spy(prefix):seen.append(prefix[-1]['date']);return indicators(prefix)
        r=replay(b,spy,CAL)
        self.assertEqual(r['anchorCount'],30);self.assertEqual(seen,[x['date'] for x in b[-30:]])
        self.assertEqual([h['done'] for h in r['reports']],[27,25])
        self.assertEqual([h['pending'] for h in r['reports']],[3,5])
    def test_future_price_mutation_cannot_change_previous_predictions(self):
        b=bars();other=deepcopy(b)
        for row in other[-10:]:
            for k in ['open','high','low','close']:row[k]*=1.1
        first=replay(b,indicators,CAL);changed=replay(other,indicators,CAL)
        for a,c in zip(first['reports'][0]['rows'][:20],changed['reports'][0]['rows'][:20]):
            self.assertEqual((a['bias'],a['score'],a['inputThrough']),(c['bias'],c['score'],c['inputThrough']))
        self.assertNotEqual(first['reports'][0]['rows'][19]['return'],changed['reports'][0]['rows'][19]['return'])
    def test_future_action_not_used_for_signal_but_outcome_excluded(self):
        b=bars();event=dict(date=b[-5]['date'],kind='減資',manualReview=True)
        plain=replay(b,indicators,CAL);changed=replay(b,indicators,CAL,[event])
        self.assertEqual(plain['reports'][0]['rows'][20]['score'],changed['reports'][0]['rows'][20]['score'])
        self.assertTrue(any(r['status']=='跨公司行動，排除' for r in changed['reports'][0]['rows']))
    def test_missing_scheduled_day_not_replaced_and_input_preserved(self):
        b=bars();removed=b[-12]['date'];b=[r for r in b if r['date']!=removed];original=deepcopy(b)
        r=replay(b,indicators,CAL)
        self.assertEqual(b,original)
        self.assertTrue(any(row['status']=='缺指定日線' for row in r['reports'][0]['rows']))
