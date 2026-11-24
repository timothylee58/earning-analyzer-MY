"""Scrape recent Bursa quarterly reports, extract text, and run the pipeline.

Usage:
    python manage.py scrape_bursa --pages 2 --analyze
"""

from django.core.management.base import BaseCommand, CommandError
import requests
from django.utils.dateparse import parse_datetime

from apps.nlp.ensemble import analyze_document
from apps.scraper import bursa
from apps.scraper.models import AnalysisResult, Announcement, Company
from apps.scraper.pdf_extract import extract_narrative
from apps.signals.fls import extract_fls


class Command(BaseCommand):
    help = "Scrape Bursa quarterly report announcements and optionally analyze them"

    def add_arguments(self, parser):
        parser.add_argument("--pages", type=int, default=1)
        parser.add_argument("--analyze", action="store_true")

    def handle(self, *args, **options):
        try:
            self._scrape(options)
        except requests.RequestException as exc:
            raise CommandError(str(exc)) from exc

    def _scrape(self, options):
        new = 0
        for page in range(1, options["pages"] + 1):
            for raw in bursa.fetch_announcements(page=page):
                row = bursa.parse_row(raw)
                if not row.get("ann_id"):
                    continue
                company, _ = Company.objects.get_or_create(
                    stock_code=row.get("company", "")[:10] or "UNKNOWN",
                    defaults={"name": row.get("company", "")},
                )
                ann, created = Announcement.objects.get_or_create(
                    ann_id=str(row["ann_id"]),
                    defaults={
                        "company": company,
                        "title": row.get("title", ""),
                        "announced_at": parse_datetime(row.get("date", ""))
                        or parse_datetime("1970-01-01T00:00:00Z"),
                    },
                )
                if not created:
                    continue
                new += 1
                if row.get("url"):
                    pdf_url = bursa.resolve_pdf_url(row["url"])
                    if pdf_url:
                        ann.pdf_url = pdf_url
                        path = bursa.download_pdf(pdf_url)
                        ann.pdf_path = str(path)
                        ann.raw_text = extract_narrative(path)
                        ann.save()
                        if options["analyze"] and ann.raw_text:
                            self._analyze(ann)
        self.stdout.write(self.style.SUCCESS(f"Ingested {new} new announcements"))

    def _analyze(self, ann: Announcement):
        doc = analyze_document(ann.raw_text)
        fls = extract_fls(ann.raw_text)
        AnalysisResult.objects.update_or_create(
            announcement=ann,
            defaults={
                "sentiment_label": doc.label,
                "sentiment_score": doc.score,
                "n_sentences": doc.n_sentences,
                "n_xlmr_sentences": doc.model_mix.get("xlm-roberta", 0),
                "fls_count": len(fls),
            },
        )
        self.stdout.write(f"  {ann.ann_id}: {doc.label} ({doc.score})")
