import unittest

from scraper.adapters import candidates, detect, probe
from scraper.http import HttpError


class Candidates(unittest.TestCase):
    def test_board_urls(self):
        cases = {
            "https://boards.greenhouse.io/examplestudio": ("greenhouse", "examplestudio"),
            "https://job-boards.greenhouse.io/acme/jobs/1": ("greenhouse", "acme"),
            "https://boards.greenhouse.io/embed/job_board?for=acme": ("greenhouse", "acme"),
            "https://jobs.lever.co/examplebrand/8f1c-1": ("lever", "examplebrand"),
            "https://jobs.ashbyhq.com/example-ai": ("ashby", "example-ai"),
            "https://apply.workable.com/acme/": ("workable", "acme"),
            "https://careers.smartrecruiters.com/Acme": ("smartrecruiters", "Acme"),
            "https://acme.recruitee.com/": ("recruitee", "acme"),
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(candidates(url), [expected])

    def test_company_domain_has_no_candidates(self):
        self.assertEqual(candidates("https://acme.com/careers"), [])

    def test_embedded_script_in_html(self):
        html = '<script src="https://boards.greenhouse.io/embed/job_board/js?for=acme"></script>'
        self.assertEqual(candidates(html), [("greenhouse", "acme")])

    def test_dedupes_and_skips_non_boards(self):
        html = 'https://jobs.lever.co/acme https://jobs.lever.co/acme/123 https://boards.greenhouse.io/embed'
        self.assertEqual(candidates(html), [("lever", "acme")])


class Detect(unittest.TestCase):
    def test_confirms_candidate_from_page(self):
        def get_text(url):
            return '<a href="https://jobs.lever.co/acme">Jobs</a>'

        def get_json(url):
            self.assertIn("api.lever.co/v0/postings/acme", url)
            return [{"id": "1"}, {"id": "2"}]

        self.assertEqual(detect("https://acme.com/careers", get_json, get_text), ("lever", "acme", 2))

    def test_none_when_endpoint_dead(self):
        def get_json(url):
            raise HttpError(url, 404, "Not Found")

        self.assertIsNone(detect("https://jobs.lever.co/acme", get_json, lambda u: ""))

    def test_none_when_page_unreachable(self):
        def get_text(url):
            raise HttpError(url, None, "timeout")

        self.assertIsNone(detect("https://acme.com/careers", lambda u: [], get_text))

    def test_probe_reports_error(self):
        def get_json(url):
            raise HttpError(url, 500, "boom")

        ok, count, err = probe("greenhouse", "acme", get_json)
        self.assertFalse(ok)
        self.assertEqual(count, 0)
        self.assertIn("500", err)

    def test_probe_unknown_kind(self):
        self.assertFalse(probe("manual", None, lambda u: {})[0])
