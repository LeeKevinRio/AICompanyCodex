import tempfile
import unittest
from unittest.mock import MagicMock, patch

from workapp.browser104 import page_total
from workapp.domain import validate_filters
from workapp.service import Service


def card(job):
    return f'<div class="info-container"><div class="info-job"><a href="https://www.104.com.tw/job/{job}">Unity 工程師</a></div><a data-gtm-joblist="職缺-地區-台北市">台北市</a></div>'


class Browser104Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = Service(self.temp.name+'/db')
        self.reader = self.service.search104.browser
        self.reader.update(keyword='Unity')
        self.runtime = MagicMock()
        self.browser = self.runtime.chromium.launch.return_value
        self.tab = self.browser.new_context.return_value.new_page.return_value
        self.tab.title.return_value = '104 Unity'
        self.body = MagicMock()
        self.next = MagicMock()
        self.tab.locator.side_effect=lambda selector:self.body if selector=='body' else self.next
        self.next.count.return_value=1
        self.manager = MagicMock()
        self.manager.__enter__.return_value = self.runtime

    def tearDown(self):
        self.temp.cleanup()

    def run_reader(self, resume=False):
        with patch('playwright.sync_api.sync_playwright', return_value=self.manager):
            self.reader.run('Unity', resume)

    def test_pages_deduplicate_and_verify_completion(self):
        self.body.inner_text.return_value='共 3 筆'
        self.tab.content.side_effect=[card('a')+card('b'),card('b')+card('c')]
        self.next.first.is_enabled.side_effect=[True,False]
        self.run_reader()
        result=self.reader.status()
        self.assertEqual((result['state'],result['pages'],result['count']),('complete',2,3))
        self.next.first.click.assert_called_once()
        self.browser.close.assert_called_once()
        self.service.search104.fetcher=MagicMock(side_effect=AssertionError('API must not be called'))
        found=self.service.search104.search(validate_filters({'keyword':'Unity','region':'taiwan'}))
        self.assertEqual(len(found['results']),3)
        self.assertEqual(found['state'],'ready')

    def test_missing_next_does_not_claim_complete_and_resume(self):
        self.body.inner_text.return_value='共 3 筆'
        self.tab.content.return_value=card('a')+card('b')
        self.next.count.return_value=0
        self.run_reader()
        self.assertEqual(self.reader.status()['state'],'partial')
        self.tab.content.return_value=card('c')
        self.run_reader(True)
        self.assertIn('page=2',self.tab.goto.call_args.args[0])
        self.assertEqual(self.reader.status()['count'],3)
        self.assertEqual(self.reader.status()['state'],'complete')

    def test_navigation_failure_preserves_rows_and_cursor(self):
        self.body.inner_text.return_value='共 3 筆'
        self.tab.content.return_value=card('a')
        self.next.first.click.side_effect=ValueError('offline')
        self.run_reader()
        saved,_=self.reader.saved('unity')
        self.assertEqual(saved['next_page'],2)
        self.assertEqual(len(saved['jobs']),1)
        self.assertEqual(saved['progress']['state'],'partial')
        self.tab.goto.side_effect=ValueError('offline again')
        self.run_reader(False)
        retained,_=self.reader.saved('unity')
        self.assertEqual(len(retained['jobs']),1)
        self.assertEqual(retained['jobs'][0]['read_at'],saved['jobs'][0]['read_at'])

    def test_explicit_zero_and_total_parser(self):
        self.assertEqual(page_total('共 1,200 筆'),1200)
        self.assertIsNone(page_total('驗證中'))
        # A zero counter alone can be a loading placeholder, never proof of no jobs.
        self.body.inner_text.side_effect=['共 0 筆','共 1 筆','共 1 筆']
        self.tab.content.side_effect=['<body>載入中</body>',card('a')]
        self.next.count.return_value=0
        self.run_reader()
        self.assertEqual(self.reader.status()['count'],1)

    def test_invalid_keyword_and_concurrent_start(self):
        for text in ('','Unity,Python','x'*201):
            with self.assertRaises(ValueError): self.reader.start(text)
        self.reader.thread=MagicMock()
        self.reader.thread.is_alive.return_value=True
        with self.assertRaises(ValueError):self.reader.start('Unity')

    def test_verification_waits_for_person_and_can_stop(self):
        self.body.inner_text.return_value='Verify you are human'
        self.tab.wait_for_timeout.side_effect=lambda _:self.reader.cancel.set()
        self.run_reader()
        self.assertEqual(self.reader.status()['state'],'paused')
        self.tab.content.assert_not_called()
        self.next.first.click.assert_not_called()
        self.browser.close.assert_called_once()
