import json

from django.test import Client, TestCase

from .ensemble import SentenceAnalysis, aggregate, analyze_document
from .hf_client import _lexicon_score
from .router import FINBERT, XLMR, route_document, route_sentence, split_sentences


class RouterTests(TestCase):
    def test_formal_english_routes_to_finbert(self):
        r = route_sentence(
            "The Group recorded a profit before tax of RM12.4 million for the quarter."
        )
        self.assertEqual(r.model, FINBERT)

    def test_bahasa_malaysia_routes_to_xlmr(self):
        r = route_sentence(
            "Kumpulan menjangka prestasi yang kukuh untuk suku tahunan akan datang."
        )
        self.assertEqual(r.model, XLMR)

    def test_manglish_particle_forces_xlmr(self):
        r = route_sentence("The revenue growth quite strong lah this quarter.")
        self.assertEqual(r.model, XLMR)

    def test_mixed_document_routes_per_sentence(self):
        text = (
            "Revenue increased 15% year on year. "
            "Prestasi kumpulan dijangka kukuh dan akan terus meningkat. "
            "Management expects margins to improve."
        )
        routed = route_document(text)
        self.assertEqual([r.model for r in routed], [FINBERT, XLMR, FINBERT])

    def test_split_sentences(self):
        self.assertEqual(len(split_sentences("One. Two! Three?")), 3)
        self.assertEqual(split_sentences(""), [])


class LexiconScorerTests(TestCase):
    def test_positive_english(self):
        r = _lexicon_score("Strong profit growth and record revenue.", "m")
        self.assertEqual(r["label"], "positive")

    def test_negative_bm(self):
        r = _lexicon_score("Kerugian meningkat dan prestasi lemah.", "m")
        self.assertEqual(r["label"], "negative")

    def test_neutral(self):
        r = _lexicon_score("The quarter ended on 31 March 2026.", "m")
        self.assertEqual(r["label"], "neutral")


class EnsembleTests(TestCase):
    def _s(self, label, score, model="finbert"):
        return SentenceAnalysis("x", model, label, score, "lexicon")

    def test_empty_document_is_neutral(self):
        doc = aggregate([])
        self.assertEqual(doc.label, "neutral")
        self.assertEqual(doc.n_sentences, 0)

    def test_confidence_weighting(self):
        doc = aggregate([self._s("positive", 0.9), self._s("negative", 0.3)])
        self.assertEqual(doc.label, "positive")
        self.assertGreater(doc.score, 0)

    def test_dead_zone_yields_neutral(self):
        doc = aggregate([self._s("positive", 0.5), self._s("negative", 0.5)])
        self.assertEqual(doc.label, "neutral")

    def test_model_mix_counts(self):
        doc = aggregate(
            [self._s("positive", 0.9), self._s("neutral", 0.6, model="xlm-roberta")]
        )
        self.assertEqual(doc.model_mix, {"finbert": 1, "xlm-roberta": 1})

    def test_analyze_document_end_to_end_offline(self):
        doc = analyze_document(
            "The Group achieved record profit growth. "
            "Keuntungan kumpulan meningkat dengan kukuh."
        )
        self.assertEqual(doc.label, "positive")
        self.assertEqual(doc.n_sentences, 2)
        self.assertIn("xlm-roberta", doc.model_mix)


class ApiTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)

    def test_analyze_requires_text(self):
        resp = self.client.post(
            "/api/analyze", data="{}", content_type="application/json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_analyze_returns_sentiment_and_fls(self):
        text = (
            "Revenue grew strongly this quarter. "
            "The Group expects margins to improve in FY2027."
        )
        resp = self.client.post(
            "/api/analyze",
            data=json.dumps({"text": text}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["sentiment"]["label"], "positive")
        self.assertEqual(len(body["forward_looking_statements"]), 1)
