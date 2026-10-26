import unittest
from copy import deepcopy
from stockapp.analysis import indicators
from stockapp.candidate_research import signal,summary,choose,study,cost_diagnostic
from stockapp.tests.test_walk_forward import bars,CAL

class CandidateTests(unittest.TestCase):
    def test_abstain_is_not_error_or_fake_accuracy(self):
        b=bars();r=study(b,indicators,CAL)
        self.assertEqual(len(r['signals']),6)
        for h in r['reports']:
            self.assertLess(h['trainingLastTarget'],h['reviewFrom'])
            for c in h['candidates']:
                self.assertLessEqual(c['review']['signals'],c['review']['eligible'])
                if not c['review']['signals']:self.assertIsNone(c['review']['hitRate'])
    def test_review_prices_cannot_change_training_or_selection(self):
        b=bars();other=deepcopy(b)
        for i,row in enumerate(other[-90:]):
            for k in ['open','high','low','close']:row[k]*=1+.001*i
        a=study(b,indicators,CAL);c=study(other,indicators,CAL)
        for x,y in zip(a['reports'],c['reports']):
            self.assertEqual(x['winner'],y['winner'])
            self.assertEqual([z['training'] for z in x['candidates']],[z['training'] for z in y['candidates']])
    def test_selection_requires_sample_coverage_edge_and_ignores_review(self):
        def c(s,n=30,coverage=.3,edge=1):return dict(id=s,training=dict(signals=n,coverage=coverage,edge=edge),review={'hitRate':100})
        self.assertIsNone(choose([c('small',29),c('sparse',coverage=.29),c('weak',edge=0)]))
        options=[c('a',edge=2),c('b',edge=1)];options[0]['review']['hitRate']=0
        self.assertEqual(choose(options),'a')
    def test_signal_rules_distinguish_horizons_and_abstain(self):
        b=bars();t=dict(atr=1,ma={'5':120,'20':110,'60':100},rsi=50,volumeRatio=1,macd=2,macdSignal=1,score=80)
        f=lambda _:t
        self.assertIsNone(signal('selective3',b,f)['bias'])
        self.assertEqual(signal('selective5',b,f)['bias'],'偏多')
        self.assertEqual(signal('trend5',b,f)['bias'],'偏多')
        self.assertIsNone(signal('trend3',b,f)['bias'])
        self.assertIsNone(signal('reversal3',b,f)['bias'])
        self.assertIsNone(signal('reversal5',b,f)['bias'])
    def test_baselines_use_identical_signal_windows(self):
        base=[dict(asOf=str(i),status='已核對',hit=i==0,realized='偏多') for i in range(3)]
        candidate=[dict(asOf='0',status='已核對',bias='偏多',realized='偏多',hit=True),dict(asOf='1',status='不評估',bias=None)]
        r=summary(candidate,base)
        self.assertEqual((r['hitRate'],r['constantRate'],r['v4Rate']),(100,100,100))
        self.assertEqual(r['coverage'],1/3)
        self.assertEqual(r['abstentions'],1)
    def test_costs_use_next_open_fixed_nonoverlapping_slots_no_short(self):
        b=bars()[:10];base=[dict(asOf=b[i]['date'],endDate=b[i+3]['date'],status='已核對') for i in range(7)]
        rows=[dict(r,bias='偏多') for r in base]
        low=cost_diagnostic(rows,base,b,.2);high=cost_diagnostic(rows,base,b,1)
        self.assertEqual(low['slots'],3);self.assertEqual(low['trades'],3)
        self.assertGreater(low['netReturn'],high['netReturn'])
        self.assertAlmostEqual(low['netReturn'],low['baselineReturn'])
        expected=1
        for i in (0,3,6):expected*=b[i+3]['close']/b[i+1]['open']-.002
        self.assertAlmostEqual(low['netReturn'],(expected-1)*100)
        short=cost_diagnostic([dict(r,bias='偏空') for r in base],base,b,.5)
        self.assertEqual((short['trades'],short['netReturn']),(0,0))
    def test_short_history_no_selection(self):
        r=study(bars()[:40],indicators,CAL)
        self.assertTrue(all(h['winner'] is None for h in r['reports']))
    def test_new_forward_day_does_not_move_historical_split_or_results(self):
        from datetime import date,timedelta
        b=bars();day=date.fromisoformat(b[-1]['date'])
        while day.isoformat()<'2026-10-22':
            day+=timedelta(days=1)
            if day.weekday()<5:b.append(dict(b[-1],date=day.isoformat()))
        before=study(b,indicators,CAL)
        after=study(b+[dict(b[-1],date='2026-10-23',close=b[-1]['close']+1)],indicators,CAL)
        self.assertEqual(before['reports'],after['reports'])
        self.assertEqual(after['signals'][0]['asOf'],'2026-10-23')
