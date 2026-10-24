import unittest
from stockapp.update_market_data import source_health

class HealthTests(unittest.TestCase):
    def test_failure_preserves_actual_success_not_attempt_time(self):
        old=dict(sourceStatus=[dict(id='https://x/a',lastSuccessAt='old')])
        events=[dict(source='https://x/a?from=old')]
        r=source_health(old,['https://x/a?from=new'],['https://x/a?from=new'],'now',events)[0]
        self.assertEqual(r['lastSuccessAt'],'old');self.assertEqual(r['lastAttemptAt'],'now')
        self.assertTrue(r['retained']);self.assertEqual(r['eventCount'],1)
    def test_legacy_failure_never_invents_success_and_empty_success_is_valid(self):
        r=source_health({},['https://x/a','https://x/b'],['https://x/a'],'now',[])
        self.assertIsNone(r[0]['lastSuccessAt']);self.assertFalse(r[0]['retained'])
        self.assertEqual(r[1]['status'],'ok');self.assertEqual(r[1]['lastSuccessAt'],'now')
        self.assertEqual(r[1]['eventCount'],0)
