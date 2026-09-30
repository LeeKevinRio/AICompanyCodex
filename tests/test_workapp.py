import concurrent.futures
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from workapp.domain import matches, salary_fields, validate_filters
from workapp.providers import normalize
from workapp.server import make_handler
from workapp.service import Service


def job(source="appier", identifier=1, **changes):
    result = normalize(source, {"id": identifier, "title": "Python Engineer", "location": {"name": "Taipei, Taiwan"}, "absolute_url": "https://example.com/job", "company_name": "Appier", "content": "Build tools", "departments": [], "first_published": "2026-09-30T00:00:00Z"})
    return result | changes


class FilteringTests(unittest.TestCase):
    def test_taiwan_does_not_mean_every_remote_job(self):
        usa = normalize("remotive", {"id": 1, "title": "Python", "company_name": "A", "url": "https://remotive.com/test", "candidate_required_location": "USA", "description": "Taiwan is mentioned in company history"})
        worldwide = usa | {"taiwan": True, "location": "Worldwide"}
        filters = validate_filters({})
        self.assertFalse(matches(usa, filters))
        self.assertTrue(matches(worldwide, filters))

    def test_remote_not_inferred_from_description(self):
        self.assertEqual(job(description="We use remote servers")["remote"], "unknown")
        self.assertFalse(matches(job(), validate_filters({"remote": "remote"})))

    def test_salary_units_unknown_and_upper_bound(self):
        filters = validate_filters({"salary_min": 60000})
        paid = job(**salary_fields("TWD 50,000–80,000 / month"))
        self.assertTrue(matches(paid, filters))
        self.assertFalse(matches(paid | {"currency": "USD", "period": "year"}, filters))
        self.assertFalse(matches(job(), filters))
        self.assertTrue(matches(job(), filters | {"include_unknown": True}))
        self.assertFalse(matches(paid, filters | {"salary_min": 90000}))

    def test_salary_does_not_guess_dollars_or_period(self):
        self.assertIsNone(salary_fields("$80k–100k")["salary_max"])
        self.assertEqual(salary_fields("USD 80k - 100k annually")["salary_max"], 100000)

    def test_keywords_or_and_case_insensitive(self):
        self.assertTrue(matches(job(), validate_filters({"keyword": "Design，PYTHON"})))
        self.assertFalse(matches(job(), validate_filters({"keyword": "Design"})))

    def test_invalid_inputs(self):
        for data in [{"salary_min": "nan"}, {"salary_min": -1}, {"region": "mars"}, {"salary_unit": "EUR/hour"}, []]:
            with self.assertRaises(ValueError):
                validate_filters(data)


class MonitoringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = 1000000
        self.items = [job()]
        self.calls = []
        self.failure = False
        def fetch(key):
            self.calls.append(key)
            if key == "appier":
                if self.failure:
                    raise RuntimeError("source unavailable")
                return self.items
            return []
        self.service = Service(Path(self.temp.name)/"db.sqlite", fetcher=fetch, clock=lambda:self.now)
        self.rule = self.service.add_rule({"name": "Python", "hours": 6, "filters": {"keyword": "python"}})

    def tearDown(self):
        self.temp.cleanup()

    def test_new_jobs_deduplicated_with_concurrent_scans(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            counts = list(pool.map(lambda _:self.service.scan(self.rule)["new_count"], range(2)))
        self.assertEqual(sum(counts), 1)
        self.assertEqual(len(self.service.discoveries(self.rule)), 1)

    def test_schedule_survives_restart_and_obeys_pause(self):
        self.service.tick()
        self.assertEqual(len(self.calls), 3)
        self.now += 6 * 3600
        self.items.append(job(identifier=2))
        restarted = Service(self.service.database, fetcher=self.service.fetcher, clock=lambda:self.now)
        restarted.tick()
        self.assertEqual(restarted.rules()[0]["latest"]["new_count"], 1)
        restarted.update_rule(self.rule, True)
        self.now += 6 * 3600
        restarted.tick()
        self.assertEqual(len(restarted.discoveries(self.rule)), 2)
        restarted.update_rule(self.rule, False)
        restarted.tick()
        self.assertEqual(restarted.rules()[0]["last_run"], self.now)

    def test_source_failure_preserves_results_and_warnings(self):
        self.service.scan(self.rule)
        self.failure = True
        self.now += 21600
        result = self.service.scan(self.rule)
        self.assertEqual(result["matches"], 1)
        self.assertEqual(result["warnings"][0]["source"], "Appier 招募")
        self.assertTrue(self.service.discoveries(self.rule)[0]["active"])

    def test_missing_job_only_closed_after_successful_refresh(self):
        self.service.scan(self.rule)
        self.items = []
        self.now += 21600
        self.service.scan(self.rule)
        self.assertEqual(self.service.jobs(validate_filters({})), [])
        self.assertFalse(self.service.discoveries(self.rule)[0]["active"])

    def test_cache_shared_between_rules_and_persistent(self):
        self.service.refresh()
        restarted = Service(self.service.database, fetcher=self.service.fetcher, clock=lambda:self.now)
        restarted.refresh()
        self.assertEqual(len(self.calls), 3)
        self.now += 1800
        restarted.refresh()
        self.assertEqual(self.calls.count("remotive"), 1)

    def test_delete_cascades_and_reject_invalid_frequency(self):
        self.service.scan(self.rule)
        self.service.delete_rule(self.rule)
        self.assertEqual(self.service.rules(), [])
        self.assertEqual(self.service.discoveries(self.rule), [])
        with self.assertRaises(ValueError):
            self.service.add_rule({"name":"bad", "hours": 1})

    def test_http_api_and_cross_origin_write_protection(self):
        server = ThreadingHTTPServer(("127.0.0.1",0), make_handler(self.service))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        try:
            with urllib.request.urlopen(url+"/api/jobs") as response:
                self.assertEqual(json.load(response)["total"], 1)
            request = urllib.request.Request(url+"/api/scan",data=json.dumps({"id":self.rule}).encode(),headers={"Content-Type":"application/json", "Origin":"https://other.example"})
            with self.assertRaises(urllib.error.HTTPError) as result:
                urllib.request.urlopen(request)
            self.assertEqual(result.exception.code, 403)
            request = urllib.request.Request(url+"/api/scan",data=json.dumps({"id":self.rule}).encode(),headers={"Content-Type":"application/json"})
            with urllib.request.urlopen(request) as response:
                self.assertEqual(json.load(response)["new_count"], 1)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
