import tempfile
import unittest
from workapp.domain import validate_filters
from workapp.platforms import PlatformSearch, job, parse_cards
from workapp.service import Service

class PlatformTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.calls=[];self.now=100000
  self.service=Service(self.tmp.name+'/db',fetcher=lambda _:[],clock=lambda:self.now)
  def fetch(source,f):
   self.calls.append((source,f['keyword']))
   return [job(source,'Unity engineer','Company','Taipei, Taiwan','https://www.linkedin.com/jobs/view/1234567',salary='TWD 60000 month')]
  self.service.platforms=PlatformSearch(self.service.db,fetch,lambda:self.now)
  self.f=validate_filters({'keyword':'Unity','sources':['linkedin']})
 def tearDown(self):self.tmp.cleanup()
 def test_selected_sources_and_scan_persist(self):
  found,status=self.service.search_all(self.f)
  self.assertEqual(len(found),1);self.assertEqual([s['id'] for s in status],['linkedin'])
  rid=self.service.add_rule({'name':'test','hours':6,'filters':self.f})
  self.assertEqual(self.service.scan(rid)['new_count'],1)
  self.assertEqual(self.service.scan(rid)['new_count'],0)
  self.assertEqual(len(self.calls),1)
  self.assertEqual(self.service.discoveries(rid)[0]['source'],'linkedin')
 def test_cache_scope_and_failure(self):
  self.service.search_all(self.f)
  self.service.search_all(self.f|{'keyword':'Python'})
  self.assertEqual(len(self.calls),2)
  self.now+=1801
  def fail(*_):raise RuntimeError('failed')
  self.service.platforms.fetcher=fail
  jobs,status=self.service.search_all(self.f)
  self.assertEqual(len(jobs),1);self.assertTrue(status[0]['error'])
 def test_source_validation(self):
  for sources in ([],['bad'],'linkedin'):
   with self.assertRaises(ValueError):validate_filters({'sources':sources})
 def test_no_keywords_does_not_fetch(self):
  jobs,status=self.service.search_all(self.f|{'keyword':''})
  self.assertEqual(jobs,[]);self.assertEqual(status[0]['state'],'skipped');self.assertEqual(self.calls,[])
 def test_parser_and_changed_page(self):
  html='''<li><h3 class="base-search-card__title">Unity engineer</h3><h4 class="base-search-card__subtitle">Company</h4><span class="job-search-card__location">Taipei</span><a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/1234567?tracking=abc"></a><time datetime="2026-10-01"></time></li>'''
  result=parse_cards('linkedin',html,'https://www.linkedin.com')
  self.assertEqual(result[0]['published'],'2026-10-01');self.assertTrue(result[0]['taiwan'])
  with self.assertRaises(ValueError):parse_cards('linkedin','<html>captcha</html>','https://www.linkedin.com')
 def test_unknown_remote_region_not_worldwide(self):
  r=job('remoteok','Unity developer','C','Remote','https://remoteok.com/remote-jobs/123',remote='remote')
  self.assertFalse(r['taiwan']);self.assertIsNone(r['salary_max'])
