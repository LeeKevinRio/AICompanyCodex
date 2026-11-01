import unittest
from stockapp.financial_context import build_context, parse_cashflows


class FinancialContextTests(unittest.TestCase):
    def test_etf_not_applicable_and_no_company_network_request(self):
        def fail_fetch(*args, **kwargs):
            self.fail('ETF must not fetch company statements')
        value = build_context('00685L', 'tse', fail_fetch, '2026-11-01')
        self.assertEqual(value['cashFlow']['status'], 'not_applicable')
        self.assertEqual(value['guidance'], [])
        self.assertIsNone(value['cashFlow']['FCF'])

    def test_aggregator_ytd_and_correct_net_operating_cash(self):
        rows = [dict(date='2026-09-30', stock_id='2383', type=t, value=v) for t,v in (
            ('CashFlowsFromOperatingActivities',12292912000),
            ('CashReceivedThroughOperations',17308723000),
            ('PropertyAndPlantAndEquipment',-16878460000),
            ('CashProvidedByInvestingActivities',-18496400000))]
        value = parse_cashflows(dict(status=200,data=rows), '2383', '2026-11-01', 'fixture')
        self.assertEqual(value['FCF'], -4585548000)
        self.assertEqual(value['unit'], 'NTD')
        self.assertEqual(value['periodType'], 'year_to_date')
        self.assertIsNone(value['publishedAt'])

    def test_positive_ppe_ambiguous_not_silently_abs(self):
        rows = [dict(date='2026-09-30', stock_id='2383', type=t, value=v) for t,v in (
            ('CashFlowsFromOperatingActivities',10), ('PropertyAndPlantAndEquipment',4))]
        self.assertIsNone(parse_cashflows(dict(status=200,data=rows),'2383','2026-11-01','fixture'))

    def test_ppe_cashflow_and_reported_precision_are_separate(self):
        value = build_context('2330', 'tse', as_of='2026-11-01')
        cash = value['cashFlow']
        self.assertEqual(cash['FCF'], cash['CFO'] - cash['PPEcapex'])
        self.assertEqual(cash['FCF'], 476570)
        self.assertEqual(cash['reportedFCF'], 476560)
        self.assertIsNone(cash['intangibleCapex'])
        self.assertFalse(value['historicalUseAllowed'])
        self.assertIsNone(value['directionOverride'])

    def test_no_unpublished_snapshot(self):
        value = build_context('2330', 'tse', as_of='2026-10-14')
        self.assertIsNone(value['cashFlow']['FCF'])
        self.assertEqual(value['guidance'], [])

    def test_unknown_company_not_zero_or_fabricated(self):
        value = build_context('2383', 'tse', as_of='2026-11-01')
        self.assertIsNone(value['cashFlow']['FCF'])
        self.assertEqual(value['guidance'], [])

    def test_company_guidance_currency_and_dates(self):
        value = build_context('2330', 'tse', as_of='2026-11-01')
        revenue = value['guidance'][0]
        self.assertEqual((revenue['low'], revenue['high']), (52.3, 54.3))
        self.assertEqual(revenue['unit'], 'USD billion')
        self.assertEqual(revenue['type'], 'company_guidance')

    def test_stale_snapshot_marked(self):
        self.assertEqual(build_context('2330', 'tse', as_of='2027-02-01')['cashFlow']['status'], 'stale')


if __name__ == '__main__':
    unittest.main()
