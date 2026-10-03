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

 def test_linkedin_pagination_aliases_and_dedup(self):
  from workapp.platforms import fetch_linkedin
  from urllib.parse import urlparse,parse_qs
  seen=[]
  def reader(url,timeout=15):
   seen.append(url);q=parse_qs(urlparse(url).query)
   if q.get('start')==['0']:
    return '<li><h3 class="base-search-card__title">Unity Engineer</h3><a class="base-card__full-link" href="https://tw.linkedin.com/jobs/view/role-1234567"></a><span class="job-search-card__location">Taiwan</span></li>'
   return ''
  result=fetch_linkedin(self.f,reader,lambda _:None,max_pages=24)
  self.assertEqual(len(result['jobs']),1)
  self.assertEqual(result['jobs'][0]['id'],'linkedin:1234567')
  self.assertEqual(result['coverage']['pages'],6)
  self.assertTrue(any('start=1' in u for u in seen))
  self.assertTrue(any('Unity3D' in u for u in seen));self.assertTrue(any('U3D' in u for u in seen))
 def test_linkedin_detail_matches_generic_title(self):
  from workapp.platforms import fetch_linkedin,filter_summary
  def reader(url,timeout=15):
   if 'jobPosting/' in url:return '<div class="show-more-less-html__markup">熟悉 Unity 開發</div>'
   if 'start=0' in url:return '<li><h3 class="base-search-card__title">遊戲工程師</h3><a class="base-card__full-link" href="https://tw.linkedin.com/jobs/view/role-1234567"></a><span class="job-search-card__location">Taiwan</span></li>'
   return ''
  result=fetch_linkedin(self.f,reader,lambda _:None)
  self.assertEqual(result['coverage']['detail_pages'],1)
  self.assertEqual(len(filter_summary(result['jobs'],self.f)[0]),1)
 def test_partial_refresh_retains_previous_jobs(self):
  self.service.search_all(self.f);self.now+=1801
  self.service.platforms.fetcher=lambda *_:{'jobs':[],'coverage':{'limited':True,'message':'rate limited','pages':1}}
  jobs,status=self.service.search_all(self.f)
  self.assertEqual(len(jobs),1);self.assertEqual(status[0]['coverage']['pages'],1);self.assertTrue(status[0]['error'])
 def test_filter_counts_not_double_counted(self):
  from workapp.platforms import filter_summary
  jobs=[job('linkedin','Community manager','C','Taiwan','https://www.linkedin.com/jobs/view/1'),job('linkedin','Unity developer','C','London','https://www.linkedin.com/jobs/view/2')]
  filtered,reasons=filter_summary(jobs,self.f)
  self.assertEqual(filtered,[]);self.assertEqual(reasons,{'關鍵字':1,'應徵地區':1})

 def test_resume_respects_cooldown_and_passes_previous_data(self):
  self.service.search_all(self.f)
  self.service.search_all(self.f,resume=True)
  self.assertEqual(len(self.calls),1)
  self.now+=61
  previous=[]
  def fetch(source,f):
   previous.extend(f['_previous_jobs']);return f['_previous_jobs']
  self.service.platforms.fetcher=fetch
  found,status=self.service.search_all(self.f,resume=True)
  self.assertEqual(len(previous),1);self.assertEqual(len(found),1)

 def test_linkedin_resume_advances_cursor_and_preserves_details(self):
  from workapp.platforms import fetch_linkedin
  from urllib.parse import urlparse,parse_qs
  seen=[]
  def reader(url,timeout=15):
   q=parse_qs(urlparse(url).query);seen.append(q)
   offset=int(q['start'][0]);identifier=1234567+offset
   return f'<li><h3 class="base-search-card__title">Unity Engineer</h3><a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/{identifier}"></a><span class="job-search-card__location">Taiwan</span></li>'
  first=fetch_linkedin(self.f,reader,lambda _:None,max_pages=3)
  self.assertTrue(first['coverage']['limited'])
  first['jobs'][0]['description']='previous detail'
  seen.clear()
  second=fetch_linkedin(self.f|{'_resume':True,'_coverage':first['coverage'],'_previous_jobs':first['jobs']},reader,lambda _:None,max_pages=3)
  self.assertTrue(all(q['start']==['1'] for q in seen))
  self.assertEqual(second['coverage']['pages'],6)
  self.assertEqual(len(second['jobs']),2)
  self.assertEqual(second['jobs'][0]['description'],'previous detail')

 def test_repeated_page_is_not_reported_as_end(self):
  from workapp.platforms import fetch_linkedin
  html='<li><h3 class="base-search-card__title">Unity Engineer</h3><a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/1234567"></a></li>'
  result=fetch_linkedin(self.f,lambda *a,**k:html,lambda _:None)
  self.assertTrue(result['coverage']['limited'])
  self.assertEqual(result['coverage']['finished_queries'],0)
  self.assertEqual(result['coverage']['cursors'][0]['offset'],1)

 def test_comment_only_end_does_not_stop_other_queries(self):
  from workapp.platforms import fetch_linkedin
  from urllib.parse import urlparse,parse_qs
  seen=[]
  def reader(url,timeout=15):
   q=parse_qs(urlparse(url).query);seen.append(q)
   if q['keywords']==['Unity3D'] or q['start']!=['0']:return '<!DOCTYPE html>\n<!----> '
   return '<li><h3 class="base-search-card__title">Unity Engineer</h3><a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/1234567"></a></li>'
  result=fetch_linkedin(self.f,reader,lambda _:None)
  self.assertFalse(result['coverage']['limited'])
  self.assertEqual(result['coverage']['finished_queries'],3)
  self.assertTrue(any(q['keywords']==['U3D'] for q in seen))

 def test_resume_prioritizes_pending_descriptions(self):
  from workapp.platforms import fetch_linkedin
  r=job('linkedin','遊戲工程師','Company','Taiwan','https://www.linkedin.com/jobs/view/1234567');r['id']='linkedin:1234567'
  seen=[]
  def reader(url,timeout=15):
   seen.append(url);return '<div class="show-more-less-html__markup">Unity development</div>'
  coverage={'unverified_details':1,'cursors':[{'keyword':'Unity','location':'Taiwan','offset':10,'done':False}]}
  result=fetch_linkedin(self.f|{'_resume':True,'_coverage':coverage,'_previous_jobs':[r]},reader,lambda _:None)
  self.assertEqual(len(seen),1);self.assertIn('/jobPosting/',seen[0])
  self.assertEqual(result['coverage']['round_pages'],0)
  self.assertEqual(result['coverage']['unverified_details'],0)
  self.assertEqual(result['coverage']['cursors'][0]['offset'],10)
