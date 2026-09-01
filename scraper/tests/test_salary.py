import unittest

from scraper.salary import extract


class Extract(unittest.TestCase):
    def test_dollar_range(self):
        self.assertEqual(extract("Base salary $130,000 - $170,000 per year plus equity."), (130000, 170000, "USD", None))

    def test_k_range_with_dash(self):
        self.assertEqual(extract("Comp: $130k–$170k depending on experience"), (130000, 170000, "USD", None))

    def test_single_figure(self):
        self.assertEqual(extract("The salary for this role is $150,000 USD."), (150000, 150000, "USD", None))

    def test_hourly_is_annualized_and_noted(self):
        lo, hi, cur, note = extract("Rate: $85 - $95 per hour, W2.")
        self.assertEqual((lo, hi, note), (85 * 2080, 95 * 2080, "hourly"))

    def test_small_numbers_are_not_salaries(self):
        self.assertIsNone(extract("A $500 signing bonus and a $50 stipend."))

    def test_nothing(self):
        self.assertIsNone(extract("We pay competitively."))
        self.assertIsNone(extract(None))

    def test_currency_word_nearby(self):
        self.assertEqual(extract("CAD $120,000 to $140,000")[2], "CAD")
