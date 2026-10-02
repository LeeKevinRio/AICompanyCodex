import tempfile
import unittest
from workapp.service import Service
from workapp.jobs104 import Search104,normalize_104
from workapp.domain import validate_filters,keyword_matches

class Jobs104Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.service=Service(self.tmp.name+'/db');self.now=100000;self.calls=0
  self.row={'jobName':'Unity Developer','custName':'Example','jobAddrNoDesc':'台北市','salaryDesc':'月薪 50,000~80,000元','salaryLow':50000,'salaryHigh':80000,'link':{'job':'//www.104.com.tw/job/abc'},'tags':{'x':{'desc':'完全遠端'}}}
  def fetch(k):self.calls+=1;return [self.row,self.row]
  self.search=Search104(self.service.db,fetch,lambda:self.now)
 def tearDown(self):self.tmp.cleanup()
 def test_cache_filter_and_dedup(self):
  f=validate_filters({'keyword':'Unity','remote':'remote'});r=self.search.search(f)
  self.assertEqual(len(r['results']),1);self.assertEqual(r['results'][0]['salary_max'],80000)
  f['salary_min']=90000;self.assertEqual(self.search.search(f)['results'],[]);self.assertEqual(self.calls,1)
 def test_failure_retains_and_cooldown(self):
  f=validate_filters({'keyword':'Unity'});self.search.search(f);self.now+=1801
  def fail(k):raise ValueError('failure')
  self.search.fetcher=fail;r=self.search.search(f);self.assertTrue(r['stale']);self.assertEqual(r['state'],'error');self.assertEqual(len(r['results']),1)
  self.assertTrue(self.search.search(f)['cached'])
 def test_units_modes_and_urls(self):
  self.row['salaryDesc']='時薪 200元';self.assertIsNone(normalize_104(self.row)['salary_max'])
  self.row['tags']={};self.row['description']='不提供遠端';self.assertEqual(normalize_104(self.row)['remote'],'onsite')
  self.row['description']='遠端團隊協作經驗';self.assertEqual(normalize_104(self.row)['remote'],'unknown')
  self.row['link']['job']='https://evil.example/job/abc'
  with self.assertRaises(ValueError):normalize_104(self.row)
 def test_aliases(self):
  self.assertTrue(keyword_matches('u3d engineer','unity'));self.assertTrue(keyword_matches('unity engineer','u3d'));self.assertFalse(keyword_matches('community','unity'))
 def test_empty_and_multi(self):
  for k in ('','Unity,Python'):
   self.assertEqual(self.search.search(validate_filters({'keyword':k}))['state'],'needs_keyword')
  self.assertEqual(self.calls,0)

 def test_overseas_currency_is_not_assumed_twd(self):
  self.row['jobAddrNoDesc']='日本東京';self.row['salaryDesc']='月薪 50,000元'
  result=normalize_104(self.row);self.assertIsNone(result['currency']);self.assertIsNone(result['salary_max'])
  self.row['salaryDesc']='月薪 USD 50,000';self.assertEqual(normalize_104(self.row)['currency'],'USD')
  self.row['jobAddrNoDesc']='台北市';self.row['salaryDesc']='月薪人民幣 50,000';self.assertIsNone(normalize_104(self.row)['currency'])
 def test_publication_date(self):
  for date in ('20261001','2026/10/01','2026-10-01'):
   self.row['appearDate']=date;self.assertEqual(normalize_104(self.row)['published'],'2026-10-01')
  self.row['appearDate']='20260230';self.assertEqual(normalize_104(self.row)['published'],'')

class BrowserFlowTests(unittest.TestCase):
 def test_initial_403_waits_then_retries_api(self):
  from unittest.mock import MagicMock,patch
  from workapp.jobs104 import fetch_104
  tab=MagicMock();tab.goto.return_value.status=403
  tab.evaluate.side_effect=[{'status':403,'text':''},{'status':200,'text':'{"data":[{"id":1}]}'},{'status':200,'text':'{"data":[]}'}]
  ctx=MagicMock();ctx.new_page.return_value=tab
  browser=MagicMock();browser.new_context.return_value=ctx
  runtime=MagicMock();runtime.chromium.launch.return_value=browser
  manager=MagicMock();manager.__enter__.return_value=runtime
  with patch('playwright.sync_api.sync_playwright',return_value=manager):
   self.assertEqual(fetch_104('Unity'),[{'id':1}])
  self.assertEqual(tab.evaluate.call_count,3)
  self.assertEqual(tab.wait_for_function.call_count,2)
  self.assertEqual(ctx.close.call_count,2)
  browser.close.assert_called_once()
