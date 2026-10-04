import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from unittest.mock import MagicMock, patch

from workapp.browser_bridge import BrowserBridge
from workapp.domain import validate_filters
from workapp.platforms import parse_cards, wait_for_job_content, platform_base, filter_summary
from workapp.server import make_handler
from workapp.service import Service

CAKE = '<article><a class="x_jobTitle" href="/companies/team/jobs/unity">遊戲工程師</a><div class="x_description">使用 Unity 開發</div><div class="x_features">全職 台灣</div><a href="/jobs/Unity/in-Taiwan">台灣</a></article>'


class BridgeTests(unittest.TestCase):
    def test_taiwan_indeed_uses_local_site(self):
        self.assertEqual(platform_base('indeed', {'region':'taiwan'}), 'https://tw.indeed.com')
        self.assertEqual(platform_base('indeed', {'region':'global'}), 'https://www.indeed.com')

    def test_new_indeed_sibling_snippet_and_inline_highlight(self):
        def card(key, description):
            return f'<div class="cardOutline"><div class="job_seen_beacon"><h3 class="jobTitle"><a class="jcs-JobTitle" href="/rc/clk?jk={key}"><span>Artist</span></a></h3><span data-testid="text-location">台北市</span></div><div data-testid="belowJobSnippet">{description}</div></div>'
        html=card('one','opport<b>unity</b> employer')+card('two','working with <b>Unity</b> engine')
        rows=parse_cards('indeed',html,'https://tw.indeed.com')
        matched,_=filter_summary(rows,validate_filters({'keyword':'Unity'}))
        self.assertEqual(len(matched),1)
        self.assertEqual(matched[0]['id'],'indeed:two')
        self.assertEqual(rows[0]['description'],'opportunity employer')
        self.assertTrue(matched[0]['url'].startswith('https://tw.indeed.com/'))

    def test_queue_is_claimed_once_and_receives_parsed_jobs(self):
        bridge = BrowserBridge()
        with ThreadPoolExecutor() as pool:
            future = pool.submit(bridge.read, 'cake', 'https://www.cake.me/jobs?q=Unity', 2)
            task = None
            for _ in range(100):
                task = bridge.poll()
                if task: break
                time.sleep(.01)
            self.assertIsNotNone(task)
            self.assertIsNone(bridge.poll())
            bridge.submit({'id': task['id'], 'html': CAKE})
            rows = future.result()
        self.assertEqual(rows[0]['description'], '使用 Unity 開發')
        self.assertEqual(rows[0]['location'], '台灣')
        self.assertEqual(bridge.status()['pending'], 0)
        with self.assertRaises(ValueError): bridge.submit({'id': task['id'], 'html': CAKE})

    def test_timeout_cleans_queue(self):
        bridge = BrowserBridge()
        with self.assertRaisesRegex(ValueError, '逾時'):
            bridge.read('cake', 'https://www.cake.me/jobs', .01)
        self.assertIsNone(bridge.poll())

    def test_disconnect_releases_waiter(self):
        bridge = BrowserBridge()
        with ThreadPoolExecutor() as pool:
            future = pool.submit(bridge.read, 'cake', 'https://www.cake.me/jobs', 2)
            for _ in range(100):
                if bridge.poll(): break
                time.sleep(.01)
            bridge.disconnect()
            with self.assertRaisesRegex(ValueError, '已停止'): future.result()
        self.assertFalse(bridge.connected())

    def test_heartbeat_expires_and_tokens_are_unique(self):
        now = [0]
        bridge = BrowserBridge(lambda: now[0])
        self.assertFalse(bridge.connected())
        bridge.poll(); self.assertTrue(bridge.connected())
        now[0] = 71; self.assertFalse(bridge.connected())
        self.assertFalse(bridge.authorized(BrowserBridge().token))
        self.assertFalse(bridge.authorized(''))

    def test_second_page_failure_retains_first(self):
        bridge = BrowserBridge(); bridge.poll()
        rows = parse_cards('cake', CAKE, 'https://www.cake.me')
        with patch.object(bridge, 'read', side_effect=[rows, ValueError('驗證')]):
            result = bridge.fetch('cake', validate_filters({'keyword': 'Unity'}))
        self.assertEqual(len(result['jobs']), 1)
        self.assertEqual(result['coverage']['pages'], 1)
        self.assertEqual(result['coverage']['method'], 'browser_helper')
        self.assertIn('驗證', result['coverage']['message'])

    def test_repeated_page_does_not_claim_complete(self):
        bridge = BrowserBridge(); bridge.poll()
        rows = parse_cards('cake', CAKE, 'https://www.cake.me')
        with patch.object(bridge, 'read', return_value=rows):
            result = bridge.fetch('cake', validate_filters({'keyword': 'Unity'}))
        self.assertEqual(result['coverage']['pages'], 1)
        self.assertIn('重複', result['coverage']['message'])

    def test_challenge_waits_but_hard_403_stops(self):
        tab = MagicMock(); tab.title.return_value = 'Just a moment...'
        response = MagicMock(status=403, headers={'cf-mitigated':'challenge'})
        wait_for_job_content(tab, response, 'article')
        tab.wait_for_selector.assert_called_once()
        tab.wait_for_selector.side_effect = TimeoutError()
        with self.assertRaisesRegex(ValueError, '驗證尚未完成'):
            wait_for_job_content(tab, response, 'article')
        tab.reset_mock(); tab.title.return_value = 'Forbidden'; response.headers = {}
        with self.assertRaisesRegex(ValueError, 'HTTP 403'):
            wait_for_job_content(tab, response, 'article')
        tab.wait_for_selector.assert_not_called()

    def test_http_pairing_and_result_require_correct_origin_and_token(self):
        with tempfile.TemporaryDirectory() as directory:
            service = Service(directory+'/test.sqlite3')
            server = ThreadingHTTPServer(('127.0.0.1',0), make_handler(service))
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f'http://127.0.0.1:{server.server_port}'
            def request(path, body=None, **headers):
                return urllib.request.urlopen(urllib.request.Request(base+'/api/browser-helper/'+path,
                    data=json.dumps(body).encode() if body is not None else None,
                    headers={'Content-Type':'application/json', **headers}))
            try:
                for origin in ('https://evil.example', ''):
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        request('pair', {}, Origin=origin)
                    self.assertEqual(caught.exception.code,403)
                with request('pair', {}, Origin=base) as response:
                    token=json.load(response)['token']
                with self.assertRaises(urllib.error.HTTPError): request('poll')
                with self.assertRaises(urllib.error.HTTPError): request('result', {'id':'fake'}, Authorization='Bearer wrong')
                extension='chrome-extension://'+'a'*32
                with request('poll', Authorization='Bearer '+token, Origin=extension) as response:
                    self.assertEqual(response.headers['Access-Control-Allow-Origin'],extension)
                    self.assertIsNone(json.load(response)['task'])
                # Pairing cannot expose the token to the extension or any remote page.
                with self.assertRaises(urllib.error.HTTPError): request('pair', {}, Origin=extension)
            finally:
                server.shutdown(); server.server_close()

    def test_helper_cache_separate_from_failed_background_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            service = Service(directory+'/test.sqlite3')
            filters = validate_filters({'keyword':'Unity'})
            with patch('workapp.browser_bridge.fetch_platform', side_effect=ValueError('403')):
                rows, status = service.platforms.search('cake', filters)
            self.assertTrue(status['error'])
            service.browser_bridge.poll()
            with patch.object(service.browser_bridge, 'read', return_value=parse_cards('cake', CAKE, 'https://www.cake.me')) as read:
                rows, status = service.platforms.search('cake', filters)
            self.assertTrue(read.called)
            self.assertEqual(len(rows),1)
            self.assertEqual(status['coverage']['method'],'browser_helper')
