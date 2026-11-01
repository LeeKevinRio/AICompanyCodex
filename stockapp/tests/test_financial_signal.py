import unittest
from stockapp.financial_context import parse_cashflows,build_context
from stockapp.financial_signal import health_check, combine_signal

def payload(values):
    return {'status':200,'data':[dict(date=day,stock_id='2383',type=kind,value=n) for day,cfo,ppe in values for kind,n in [('CashFlowsFromOperatingActivities',cfo),('PropertyAndPlantAndEquipment',-ppe)]]}

class FinancialSignalTests(unittest.TestCase):
    def context(self,values):
        return {'asOf':'2026-11-01','cashFlow':parse_cashflows(payload(values),'2383','2026-11-01','fixture')}

    def test_ytd_subtracted_before_comparison_and_year_ago_separate(self):
        c=self.context([('2025-06-30',100,20),('2025-09-30',200,60),('2026-03-31',100,20),('2026-06-30',220,60),('2026-09-30',250,150)])
        h=health_check(c)
        self.assertEqual(h['current']['FCF'],-60)
        self.assertEqual(h['previous']['FCF'],80)
        self.assertEqual(h['yearAgo']['FCF'],60)
        self.assertEqual(h['qoq'],-175)
        self.assertIn('由正／零轉負',h['flags'])
        self.assertIn('營業現金流同步減少',h['flags'])
        self.assertEqual(h['score'],0)

    def test_no_missing_quarter_or_zero_denominator_fabrication(self):
        c=self.context([('2026-03-31',10,10),('2026-09-30',50,20)])
        self.assertFalse(health_check(c)['available'])
        c=self.context([('2026-03-31',10,10),('2026-06-30',20,25)])
        h=health_check(c)
        self.assertTrue(h['available']);self.assertIsNone(h['qoq'])

    def test_negative_recovery_still_warns_and_positive_decline_not_healthy(self):
        h=health_check(self.context([('2026-03-31',20,100),('2026-06-30',50,150)]))
        self.assertEqual(h['score'],50)
        self.assertIn('自由現金流為負',h['flags'])
        h=health_check(self.context([('2026-03-31',100,20),('2026-06-30',150,40)]))
        self.assertEqual(h['status'],'需留意')

    def test_future_period_not_used_and_old_reports_blocked(self):
        c=self.context([('2026-03-31',100,20),('2026-06-30',200,40),('2026-12-31',99999,0)])
        self.assertEqual(c['cashFlow']['quarters'][-1]['period'],'2026-Q2')
        c['asOf']='2027-11-01'
        self.assertFalse(health_check(c)['available'])

    def test_fixed_weight_can_change_direction_without_mutating_v4(self):
        tech={'score':70,'bias':'偏多'}
        result=combine_signal(tech,{'health':{'available':True,'score':0}})
        self.assertEqual(result['score'],56)
        self.assertEqual(result['bias'],'震盪')
        self.assertEqual(tech['bias'],'偏多')
        self.assertFalse(combine_signal(tech,{'health':{}})['available'])

    def test_ytd_negative_remains_risky_despite_quarter_recovery(self):
        h=health_check(self.context([('2026-03-31',10,100),('2026-06-30',40,110)]))
        self.assertEqual(h['current']['FCF'],20)
        self.assertEqual(h['score'],50)
        self.assertEqual(h['status'],'需留意')

    def test_official_latest_quarter_replaces_older_aggregator_period(self):
        data=payload([('2026-03-31',100000000000,20000000000),('2026-06-30',200000000000,40000000000)])
        for row in data['data']:row['stock_id']='2330'
        context=build_context('2330','tse',lambda url,**kwargs:data if 'CashFlows' in url else [],'2026-11-01')
        self.assertEqual(context['health']['current']['period'],'2026-Q3')
        self.assertEqual(context['health']['current']['FCF'],476570e6)
        self.assertEqual(context['health']['previous']['period'],'2026-Q2')

    def test_calendar_year_boundary_uses_q4_and_no_double_count(self):
        c=self.context([('2025-09-30',100,20),('2025-12-31',140,30),('2026-03-31',50,10)])
        c['asOf']='2026-05-01'
        h=health_check(c)
        self.assertEqual(h['previous']['period'],'2025-Q4')
        self.assertEqual(h['previous']['FCF'],30)
        self.assertEqual(h['current']['FCF'],40)
