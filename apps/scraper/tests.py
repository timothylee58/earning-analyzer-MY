from django.test import TestCase

from .bursa import parse_row, _strip_tags
from .pdf_extract import keep_prose


class ParseRowTests(TestCase):
    def test_parses_positional_html_row(self):
        row = [
            1,
            "<div>06 Jul 2026</div>",
            '<a href="/company/x">MAYBANK</a>',
            '<a href="/market_information/announcements/company_announcement/announcement_details?ann_id=3456789">Quarterly rpt on consolidated results</a>',
        ]
        parsed = parse_row(row)
        self.assertEqual(parsed["ann_id"], "3456789")
        self.assertEqual(parsed["company"], "MAYBANK")
        self.assertIn("Quarterly", parsed["title"])
        self.assertTrue(parsed["url"].startswith("https://www.bursamalaysia.com"))

    def test_dict_row_passthrough(self):
        row = {"ann_id": "1", "title": "t"}
        self.assertEqual(parse_row(row), row)

    def test_strip_tags(self):
        self.assertEqual(_strip_tags("<b>hi</b> there"), "hi there")


class ProseFilterTests(TestCase):
    def test_keeps_narrative_drops_tables(self):
        raw = "\n".join(
            [
                "Revenue 1,234 5,678 12.3% 45.6%",
                "The Group recorded higher revenue driven by loan growth.",
                "31.3.2026 31.3.2025",
                "Prospek kumpulan dijangka kekal kukuh untuk tahun kewangan ini.",
                "Note 5",
            ]
        )
        kept = keep_prose(raw)
        self.assertIn("loan growth", kept)
        self.assertIn("Prospek", kept)
        self.assertNotIn("5,678", kept)
        self.assertNotIn("Note 5", kept)
