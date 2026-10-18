import unittest
from stockapp.update_market_data import merge_action_snapshot

class RecoveryTests(unittest.TestCase):
    def test_failed_historic_family_preserves_history_and_original_freshness(self):
        event=dict(id='2330',date='2026-07-01',exchange='tse',source='https://x/TWT49U?startDate=old',referencePrice=100)
        old=dict(events=[event],fetchedAt='old',historyFrom='2025-01-01',historyTo='2026-10-16',sources=[event['source']])
        new=dict(events=[],fetchedAt='new',sources=[],historyFrom=None,historyTo=None)
        result=merge_action_snapshot(old,new,['https://x/TWT49U?startDate=new'],'attempt')
        self.assertEqual(result['events'],[event]);self.assertEqual(result['fetchedAt'],'old')
        self.assertEqual(result['historyFrom'],'2025-01-01');self.assertEqual(result['lastAttemptAt'],'attempt')
    def test_successful_empty_source_removes_old_upcoming_event(self):
        event=dict(id='2330',date='2026-07-01',exchange='tse',source='https://x/upcoming')
        result=merge_action_snapshot(dict(events=[event],fetchedAt='old'),dict(events=[],fetchedAt='new'),[],'attempt')
        self.assertEqual(result['events'],[]);self.assertEqual(result['fetchedAt'],'new')
    def test_partial_success_keeps_failed_source_and_replaces_successful_source(self):
        a=dict(id='2330',date='2026-07-01',exchange='tse',source='https://x/a')
        b=dict(id='3037',date='2026-07-01',exchange='tse',source='https://x/b')
        result=merge_action_snapshot(dict(events=[a,b],fetchedAt='old'),dict(events=[],sources=[]),['https://x/a'],'attempt')
        self.assertEqual(result['events'],[a])
