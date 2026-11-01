import json,tempfile,unittest
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
from datetime import datetime
from stockapp.daily_service import DailyService,evaluate,TZ

CAL=dict(years=[2026],closed={},opened={},unknown={})
def analysis(day='2026-10-27'):
    return dict(id='2330',asOf=day,planEnabled=True,bars=[dict(date=day,close=100)],model='規則v4',technical=dict(score=75,reasons=[]),forecasts=[dict(days=3,bias='偏多'),dict(days=5,bias='偏多')])
class DailyTests(unittest.TestCase):
    def test_daily_status_rejects_cross_origin_and_rebound_host(self):
        from stockapp.server import Handler
        for headers,expected in [({'Host':'127.0.0.1:8765'},200),({'Host':'evil.example:8765'},403),({'Host':'127.0.0.1:8765','Origin':'https://evil.example'},403)]:
            h=Handler.__new__(Handler);h.path='/api/daily-status';h.headers=headers;answers=[];h.respond=lambda status,payload:answers.append(status)
            with patch('stockapp.server.DAILY_SERVICE',SimpleNamespace(snapshot=lambda:{})):h.do_GET()
            self.assertEqual(answers,[expected])
    def test_corrupt_outcome_does_not_pass_record_validation(self):
        r=dict(key='stock:2330:2026-10-27:3:v4',kind='stock',id='2330',exchange='tse',asOf='2026-10-27',days=3,bias='偏多',baseClose=100,recordedAt='2026-10-27T10:00:00Z',model='v4')
        self.assertTrue(DailyService.valid_record(r))
        self.assertFalse(DailyService.valid_record({**r,'outcome':dict(status='已到期',return_=2,realized='偏多',hit=False,endDate='2026-10-30')}))
    def test_actual_creation_time_and_cross_midnight_never_backfill(self):
        with tempfile.TemporaryDirectory() as folder:
            s=DailyService(Path(folder)/'state.json');s.configure([dict(id='2330',exchange='tse')],True)
            start=datetime(2026,10,27,17,30,tzinfo=TZ);created=datetime(2026,10,27,17,32,tzinfo=TZ)
            times=iter([start,created])
            s.run(lambda *_:analysis(),lambda:CAL,lambda:None,clock=lambda:next(times))
            self.assertTrue(all(r['recordedAt']==created.isoformat() for r in s.state['records']))
            s=DailyService(Path(folder)/'other.json');s.configure([dict(id='2330',exchange='tse')],True)
            times=iter([start,datetime(2026,10,28,0,0,tzinfo=TZ)])
            s.run(lambda *_:analysis(),lambda:CAL,lambda:None,clock=lambda:next(times))
            self.assertEqual(s.state['records'],[])
            self.assertEqual(s.state['runs'][-1]['status'],'失敗')
    def test_save_failure_rolls_back_unpublished_predictions(self):
        with tempfile.TemporaryDirectory() as folder:
            s=DailyService(Path(folder)/'state.json');s.configure([dict(id='2330',exchange='tse')],True)
            original=s.save;calls=[]
            def flaky():
                calls.append(1)
                if len(calls)==1:raise OSError('quota')
                return original()
            s.save=flaky
            s.run(lambda *_:analysis(),lambda:CAL,lambda:None,datetime(2026,10,27,17,30,tzinfo=TZ))
            self.assertEqual(s.state['records'],[])
            self.assertEqual(json.loads(s.path.read_text(encoding='utf-8'))['records'],[])
            self.assertEqual(s.state['runs'][-1]['status'],'失敗')
    def test_same_key_never_overwrites_initial_direction(self):
        with tempfile.TemporaryDirectory() as folder:
            s=DailyService(Path(folder)/'state.json');s.configure([dict(id='2330',exchange='tse')],True)
            s.run(lambda *_:analysis(),lambda:CAL,lambda:None,datetime(2026,10,27,17,30,tzinfo=TZ))
            changed=analysis()
            for f in changed['forecasts']:f['bias']='偏空'
            s.run(lambda *_:changed,lambda:CAL,lambda:None,datetime(2026,10,27,18,30,tzinfo=TZ),force=True)
            self.assertTrue(all(r['bias']=='偏多' for r in s.state['records']))
            self.assertEqual(len(s.state['records']),2)
    def test_structurally_broken_record_blocks_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'state.json';raw=json.dumps(dict(version=1,enabled=True,targets=[],records=[{}],candidates=[],runs=[]));p.write_text(raw)
            s=DailyService(p);self.assertTrue(s.error)
            with self.assertRaises(ValueError):s.configure([],True)
            self.assertEqual(p.read_text(),raw)
    def test_no_browser_needed_dedup_and_only_today(self):
        with tempfile.TemporaryDirectory() as folder:
            service=DailyService(Path(folder)/'state.json');service.configure([dict(id='2330',exchange='tse')],True)
            service.run(lambda *_:analysis(),lambda:CAL,lambda:None,datetime(2026,10,27,17,30,tzinfo=TZ))
            self.assertEqual(len(service.state['records']),2);self.assertEqual(service.state['runs'][-1]['status'],'完成')
            again=DailyService(service.path);again.run(lambda *_:analysis(),lambda:CAL,lambda:None,datetime(2026,10,27,18,0,tzinfo=TZ),force=True)
            self.assertEqual(len(again.state['records']),2)
            again.run(lambda *_:analysis(),lambda:CAL,lambda:None,datetime(2026,10,28,18,0,tzinfo=TZ))
            self.assertEqual(len(again.state['records']),2);self.assertEqual(again.state['runs'][-1]['status'],'資料未齊')
            self.assertNotIn('shares',service.path.read_text(encoding='utf-8'));self.assertNotIn('cost',service.path.read_text(encoding='utf-8'))
    def test_corrupt_storage_not_overwritten_and_targets_cannot_include_assets(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'state.json';p.write_text('{broken');s=DailyService(p)
            with self.assertRaises(ValueError):s.configure([],True)
            self.assertEqual(p.read_text(),'{broken')
        with self.assertRaises(ValueError):DailyService.validate_targets([dict(id='2330',exchange='tse',shares=50)])
    def test_schedule_and_holidays_no_backfill(self):
        with tempfile.TemporaryDirectory() as folder:
            s=DailyService(Path(folder)/'state.json');s.configure([dict(id='2330',exchange='tse')],True)
            s.run(lambda *_:analysis(),lambda:CAL,lambda:None,datetime(2026,10,27,14,0,tzinfo=TZ));self.assertEqual(s.state['runs'],[])
            s.run(lambda *_:analysis(),lambda:CAL,lambda:None,datetime(2026,11,1,18,0,tzinfo=TZ));self.assertEqual(s.state['runs'][-1]['status'],'休市跳過');self.assertEqual(s.state['records'],[])
    def test_outcome_strict_dates_events_and_late_creation(self):
        r=dict(asOf='2026-10-27',days=3,bias='偏空',baseClose=100,recordedAt='2026-10-27T18:00:00+08:00')
        bars=[dict(date=d,close=p) for d,p in [('2026-10-27',100),('2026-10-28',99),('2026-10-29',98),('2026-10-30',97)]]
        self.assertAlmostEqual(evaluate(r,bars,CAL,[])['return_'],-3)
        self.assertIsNone(evaluate(r,bars[:2]+bars[3:],CAL,[]))
        self.assertIsNone(evaluate(r,bars,CAL,[dict(date='2026-10-29')]))
        self.assertEqual(evaluate({**r,'recordedAt':'2026-10-28T09:00:00+08:00'},bars,CAL,[])['status'],'建立過晚，不納入')
