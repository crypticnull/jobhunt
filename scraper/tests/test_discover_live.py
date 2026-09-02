"""The regression built from the first live run.

On 2026-09-02 the first real night added forty-eight companies and not one
was relevant: sales, QA, marketing, data and backend roles at Binance,
Fastly, FICO and Carter's, plus a building maintenance technician. The
company names and titles below are the real ones, recovered from the list
that run pushed. Discovery had judged relevance with the scoring
intersection legs, which match api, automation, rendering and modeling,
and every one of those postings said at least one of those words.

The feeds cannot be reached from CI, so this is the closest thing to the
live test there is: the real titles, with a description carrying the exact
broad terms that let them through the first time."""

import json
import unittest

from scraper import discover
from scraper.score import RULES_PATH, load_rules

RULES = load_rules(RULES_PATH, local="/nonexistent")

# The description every false positive effectively had: ordinary software
# and operations language. These are the words the old filter matched on.
GENERIC = (
    "We are looking for a strong contributor. You will work with our REST API, "
    "build automation, own server-side rendering and data modeling, write Python "
    "and JavaScript, improve our workflow and tooling, maintain metadata and "
    "taxonomy, and work with Node. Fully remote, competitive salary."
)

# name, title. Recovered from data/companies.json as the live run pushed it.
LIVE_RUN = [
    ("A.Team", "software development"),
    ("AlertMedia", "marketing operations specialist"),
    ("AlgaeCal", "automation qa engineer lead"),
    ("Amplify Renewables", ""),
    ("ANGI", "principal analytics engineer"),
    ("AppSamurai", "sales account executive mena region"),
    ("Ashby", ""),
    ("AssetWatch", "quality assurance engineer"),
    ("Astoria AI", ""),
    ("Astronomer", ""),
    ("Azumo", "technical leader latin america"),
    ("Binance", "bap data analyst"),
    ("Biobase", ""),
    ("Blackbird Interactive", "remote senior level designer"),
    ("Breezeway", "sales development representative"),
    ("Bright Vision Technologies", "aem technical consultant"),
    ("Brilliant.org", ""),
    ("Cardog", ""),
    ("Carters Inc.", "remote store manager"),
    ("Caylent", "senior qa engineer"),
    ("ChainSecurity", ""),
    ("Chariot Claims", ""),
    ("Charles Technology Africa", "web developer"),
    ("Chronograph", ""),
    ("CodePath", "staff software engineer"),
    ("Complex Co.", "remote commercial building estimator"),
    ("Creative Force", "customer service"),
    ("CyberAtlas", ""),
    ("Dart", "remote building maintenance technician"),
    ("Denova Consulting", "business development representative"),
    ("Deya", ""),
    ("DualEntry", ""),
    ("Dunetrace", "technical co founder"),
    ("Ehvert Engineering", "controls design engineer"),
    ("Enrollment123", ""),
    ("Entrust", "principal cloud devops engineer"),
    ("Faire", "senior staff data engineer platform data and analytics"),
    ("Fandom", "director revenue strategy commercial innovation"),
    ("Fastly", ""),
    ("FICO", "business operations lead analyst scores"),
    ("Fisher Associates", "precast design engineer"),
    ("Fivetran", "senior pricing data scientist"),
    ("Flex", "senior software engineer backend"),
    ("Food Service Specialties", "back office support"),
    ("garden3d", "head of marketing communications"),
]

# The one posting in that run that Matt should actually have seen.
KEEPER = ("CapsLock", "generative ai pipeline engineer tech lead")


def item(company, title, text=GENERIC):
    return discover._item("remotive", company, title, f"https://x/{company}", text)


class TheFortyEight(unittest.TestCase):
    def test_every_false_positive_is_rejected_now(self):
        kept = [(c, t) for c, t in LIVE_RUN if discover.relevant(item(c, t), RULES)]
        self.assertEqual(kept, [], "these are the real postings that flooded the list on 2026-09-02")

    def test_the_one_real_hit_in_that_run_survives(self):
        """CapsLock was hiring a generative AI pipeline engineer. That posting
        was the whole point, and it has to come through."""
        hits = discover.relevant(item(*KEEPER), RULES)
        self.assertIn("generative ai", hits)

    def test_the_old_broad_terms_would_have_let_them_all_through(self):
        """Why the tighter list exists: the scoring legs match every one of
        these, which is correct for a company already on the list and wrong
        for an open feed."""
        legs = [t for leg in RULES["score"]["intersection"]["legs"].values() for t in leg]
        passed = [c for c, t in LIVE_RUN if discover._hits(t + "\n" + GENERIC, legs)]
        self.assertEqual(len(passed), len(LIVE_RUN))

    def test_a_creative_role_at_any_of_these_companies_still_comes_through(self):
        """The filter is about the role, never the company. Fastly hiring a
        motion designer is a posting Matt wants."""
        hits = discover.relevant(item("Fastly", "Senior Motion Designer", "After Effects and Cinema 4D." + GENERIC), RULES)
        self.assertTrue(hits)

    def test_a_generic_company_name_from_that_run_is_dropped(self):
        """One posting arrived with the company name 'Company', and one Hacker
        News comment became a company named after an entire sentence."""
        self.assertTrue(discover._generic("Company", RULES))
        self.assertTrue(discover._generic("Beacon AI builds intelligent systems that make aviation safer", RULES))
        self.assertFalse(discover._generic("CapsLock", RULES))

    def test_top_notch_is_not_a_vfx_tool(self):
        """'notch' was in the first draft of the list. 'top-notch' is in half
        the job ads ever written."""
        self.assertEqual(discover.relevant(item("Some Co", "Engineer", "A top-notch team."), RULES), [])
