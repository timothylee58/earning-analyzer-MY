"""Analyze a manually downloaded report without the Bursa listing service."""

import json
from dataclasses import asdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.test.utils import override_settings

from apps.nlp.ensemble import analyze_document
from apps.scraper.pdf_extract import extract_narrative
from apps.signals.fls import extract_fls


class Command(BaseCommand):
    help = "Extract and analyze a local PDF; print JSON without writing database records"

    def add_arguments(self, parser):
        parser.add_argument("pdf", type=Path)
        parser.add_argument("--offline", action="store_true", help="Use the lexicon scorer; make no inference requests")

    def handle(self, *args, **options):
        path = options["pdf"].expanduser().resolve()
        try:
            with path.open("rb") as source:
                if source.read(5) != b"%PDF-":
                    raise CommandError("Input is not a PDF file.")
            text = extract_narrative(path)
        except FileNotFoundError as exc:
            raise CommandError(f"PDF not found at {path}. Upload the report or pass its workspace path.") from exc
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(f"Could not extract PDF ({type(exc).__name__}). Check the path and use an unlocked, valid PDF.") from exc
        if not text.strip():
            raise CommandError("No narrative text found. Scanned reports need OCR before analysis.")
        if options["offline"]:
            with override_settings(HF_API_TOKEN="", USE_LOCAL_INFERENCE=False):
                doc = analyze_document(text)
        else:
            doc = analyze_document(text)
        result = {
            "pdf": str(path),
            "text": text,
            "analysis": asdict(doc),
            "forward_looking_statements": extract_fls(text),
        }
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
