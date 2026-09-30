import os
import tempfile
import unittest
from unittest.mock import patch
from workapp.domain import validate_filters
from workapp.service import Service
from workapp.websearch import WebSearch, build_query, normalize_results, fetch_google

class SearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.service = Service(self.tmp.name + '/test.db')
        self.filters = validate_filters({'keyword':'Unity'})
        self.now = 100000
        self.calls = []
        self.item = {'title':'Unity Developer', 'snippet':'Unity3D development', 'link':'https://www.104.com.tw/job/abc?track=1'}
        def fetch(q,k):
            self.calls.append(q)
            return [self.item]
        self.search = WebSearch(self.service.db, fetch, lambda:self.now)
        self.env = patch.dict(os.environ, {'WORKAPP_SERPAPI_KEY':'test-only'})
        self.env.start()
    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()
    def test_cache_restart_and_query_scope(self):
        self.assertEqual(len(self.search.search(self.filters)['results']),1)
        restarted = WebSearch(self.service.db, lambda *_: self.fail('cache missed'), lambda:self.now)
        self.assertTrue(restarted.search(self.filters)['cached'])
        self.search.search(validate_filters({'keyword':'Python'}))
        self.assertEqual(len(self.calls),2)
    def test_missing_key_and_empty_keyword_do_not_call(self):
        with patch.dict(os.environ, {'WORKAPP_SERPAPI_KEY':''}):
            self.assertEqual(self.search.search(self.filters)['state'],'not_configured')
        self.assertEqual(self.search.search(validate_filters({}))['state'],'needs_keyword')
        self.assertEqual(self.calls,[])
    def test_failure_retains_expired_results_without_secret(self):
        self.search.search(self.filters)
        self.now += 21601
        def fail(*_): raise ValueError('SECRET API URL')
        self.search.fetcher = fail
        result = self.search.search(self.filters)
        self.assertEqual(result['state'],'error')
        self.assertTrue(result['stale'])
        self.assertEqual(len(result['results']),1)
        self.assertNotIn('SECRET',str(result))
    def test_limit(self):
        for i in range(10): self.search.search(validate_filters({'keyword':str(i)}))
        self.assertEqual(self.search.search(self.filters)['state'],'limited')
        self.assertEqual(len(self.calls),10)
    def test_urls_dedup_and_keyword(self):
        items = [self.item,dict(self.item,link='https://104.com.tw/job/abc'),
          dict(self.item,link='https://www.104.com.tw.evil.com/job/abc'),
          dict(self.item,link='javascript:alert(1)'),
          dict(self.item,link='https://www.104.com.tw/jobs/search/'),
          dict(self.item,title='Community manager',snippet='opportunity',link='https://www.1111.com.tw/job/123'),
          dict(self.item,link='https://www.1111.com.tw/job/234')]
        results = normalize_results(items,self.filters)
        self.assertEqual(len(results),2)
        self.assertEqual(results[0]['url'],'https://www.104.com.tw/job/abc')
    def test_query(self):
        q=build_query(validate_filters({'keyword':'Unity,C#','remote':'remote','location':'台北'}))
        self.assertIn('"Unity" OR "C#"',q)
        self.assertIn('fully remote',q)
        self.assertIn('"台北"',q)
    def test_transport_failure_sanitized(self):
        with patch('workapp.websearch.urllib.request.urlopen',side_effect=Exception('SECRET')):
            with self.assertRaises(ValueError) as error: fetch_google('q','SECRET')
        self.assertNotIn('SECRET',str(error.exception))
    def test_zero_differs_from_malformed(self):
        import io,json
        for payload,valid in [({'search_metadata':{'status':'Success'},'organic_results':[]},True),({'search_metadata':{'status':'Success'}},False)]:
            with patch('workapp.websearch.urllib.request.urlopen',return_value=io.BytesIO(json.dumps(payload).encode())):
                if valid:self.assertEqual(fetch_google('q','test'),[])
                else:
                    with self.assertRaises(ValueError):fetch_google('q','test')
