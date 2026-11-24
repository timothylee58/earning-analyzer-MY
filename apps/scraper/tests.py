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


class AccessAndPdfTests(TestCase):
    def test_challenge_becomes_actionable_command_error(self):
        from unittest.mock import patch
        from django.core.management import call_command, CommandError
        import requests
        response = requests.Response()
        response.status_code = 403
        with patch('apps.scraper.bursa.requests.get', return_value=response):
            with self.assertRaisesMessage(CommandError, 'analyze_pdf'):
                call_command('scrape_bursa')

    def test_unexpected_schema_is_not_empty_success(self):
        from unittest.mock import patch, Mock
        from .bursa import fetch_announcements, BursaAccessError
        response = Mock(status_code=200, headers={})
        response.json.return_value = {'unexpected': []}
        with patch('apps.scraper.bursa.requests.get', return_value=response):
            with self.assertRaisesMessage(BursaAccessError, 'schema changed'):
                fetch_announcements()

    def test_html_download_is_not_saved(self):
        from unittest.mock import patch, Mock
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from .bursa import download_pdf, BursaAccessError
        response = Mock(status_code=200, headers={}, content=b'<html>challenge</html>')
        with TemporaryDirectory() as directory:
            with patch('apps.scraper.bursa.requests.get', return_value=response):
                with self.assertRaises(BursaAccessError):
                    download_pdf('https://www.bursamalaysia.com/report.pdf', Path(directory))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_real_pdf_extraction_and_offline_analysis(self):
        import importlib.util
        if importlib.util.find_spec('pdfplumber') is None:
            self.skipTest('Optional PDF dependency not installed')
        import json
        from io import StringIO
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from django.core.management import call_command
        # A real, minimal PDF with an English and a BM narrative line.
        stream = b'BT /F1 12 Tf 50 750 Td (Revenue grew and profits improved.) Tj 0 -20 Td (Prestasi kumpulan dijangka kekal kukuh.) Tj ET'
        objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
                   b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                   b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
                   b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
                   b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
        pdf = b'%PDF-1.4\n'
        offsets = [0]
        for index, obj in enumerate(objects, 1):
            offsets.append(len(pdf))
            pdf += f'{index} 0 obj\n'.encode()+obj+b'\nendobj\n'
        xref = len(pdf)
        pdf += b'xref\n0 6\n0000000000 65535 f \n'
        pdf += b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:])
        pdf += f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
        with TemporaryDirectory() as directory:
            path = Path(directory)/'sample.pdf'
            path.write_bytes(pdf)
            output = StringIO()
            with patch('apps.nlp.hf_client.requests.post', side_effect=AssertionError('Network forbidden')):
                call_command('analyze_pdf', str(path), offline=True, stdout=output)
            result = json.loads(output.getvalue())
            self.assertEqual(result['analysis']['n_sentences'], 2)
            self.assertEqual(result['analysis']['model_mix'], {'finbert': 1, 'xlm-roberta': 1})
            self.assertTrue(all(s['source'] == 'lexicon' for s in result['analysis']['sentences']))
            self.assertTrue(result['forward_looking_statements'])

    def test_invalid_pdf_is_rejected(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from django.core.management import call_command, CommandError
        with TemporaryDirectory() as directory:
            path = Path(directory)/'fake.pdf'
            path.write_text('<html>not a report</html>')
            with self.assertRaisesMessage(CommandError, 'not a PDF'):
                call_command('analyze_pdf', str(path), offline=True)
