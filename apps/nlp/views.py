import json
from dataclasses import asdict

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.signals.fls import extract_fls

from .ensemble import analyze_document


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


@csrf_exempt
@require_POST
def analyze(request: HttpRequest) -> JsonResponse:
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid JSON"}, status=400)
    text = (body.get("text") or "").strip()
    if not text:
        return JsonResponse({"error": "'text' is required"}, status=400)

    doc = analyze_document(text)
    fls = extract_fls(text)
    return JsonResponse(
        {
            "sentiment": {
                "label": doc.label,
                "score": doc.score,
                "n_sentences": doc.n_sentences,
                "model_mix": doc.model_mix,
            },
            "sentences": [asdict(s) for s in doc.sentences],
            "forward_looking_statements": fls,
        }
    )
