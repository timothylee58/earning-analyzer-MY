# Optional integration setup and validation

Validation date: 24 November 2026 (Asia/Kuala_Lumpur).

## Manual PDF fallback implemented

Run `python manage.py analyze_pdf /path/to/report.pdf --offline > analysis.json`
after downloading a report through your browser from Bursa or the issuer's
investor-relations site. No database records are created. Output includes prose,
document sentiment, sentence routing/scoring sources, and forward-looking
statements. Remove `--offline` only when you want configured remote inference.

The scraper now reports access blocks as actionable command errors, rejects
unexpected listing schemas, and refuses to save non-PDF download responses.
All 36 offline tests pass, including actual extraction from a synthetic bilingual
PDF and verification that offline analysis makes no inference request. No real
quarterly PDF or accessible direct-report URL was supplied, so real-report and
live scraping validation remain outstanding. The Cloudflare challenge itself
has not been removed.

The offline Django suite passes all 31 tests. This does not establish that
remote models or the live Bursa response format work.

| Integration | Observed result |
|---|---|
| Java gateway | Maven package succeeded; live `/health` and bilingual `/analyze` returned 200 and matched Django JSON |
| Hugging Face | Token authentication passed (200); both model provider mappings report live. Inference remains blocked; see retry below. |
| Bursa | Domain reachable, but Cloudflare returns a 403 challenge; listing/PDF validation remains blocked. |

There are no Java test sources in the repository. Gateway validation covered
the build and successful forwarding, not authentication, rate limits, or failure
handling. The bilingual smoke check reported `source=lexicon` for both sentences.

## Latest retry — 24 November 2026

The published allowlist now includes all four requested domains. HF token
binding is ready, and authenticated `GET /api/whoami-v2` returned 200 (no account
or token details recorded). Both configured models report a live `hf-inference`
provider for text classification.

The existing client's `api-inference.huggingface.co` POST still fails at the
proxy with CONNECT 403 despite being listed in the policy. An unauthenticated
POST to `https://router.huggingface.co/hf-inference/models/ProsusAI/finbert`
reaches the service and returns 401. The token binding permits only
`huggingface.co` and `api-inference.huggingface.co`; add
`router.huggingface.co` to the **secret binding's allowed domains**, preserving
those existing entries. Public Internet Access alone does not grant credential
use on that host. No authenticated router request was made. Next, migrate the
client to the router endpoint and verify both models return real scores.

Bursa's one-row listing request now reaches Cloudflare but returns HTTP 403
with a “Just a moment...” challenge. This is different from the earlier
workspace proxy denial. No repeated scrape attempts or challenge bypass were
performed. Use an approved Bursa data source/access arrangement, or supply a
quarterly-report PDF for extraction validation. Listing, detail resolution,
and live PDF download are still unvalidated.

The initial findings below are retained as setup history; the latest retry
above supersedes the earlier missing-token and domain-policy findings.

## Hugging Face

No `HF_API_TOKEN` or local `.env` was configured during validation. Outbound
requests to Hugging Face were refused by the workspace proxy (CONNECT 403),
before reaching the service. The environment change tool also refused the
domain grant: “The published configuration does not allow this network access.”

1. Update the cloud environment's published network configuration to allow
   `huggingface.co`, `api-inference.huggingface.co`, and `router.huggingface.co`,
   preserving the package-manager preset. Alternatively run on your own machine
   with permitted network access.
2. Create a token at https://huggingface.co/settings/tokens with inference
   permissions. Store it as the environment secret `HF_API_TOKEN`; do not paste
   it into chat or commit it. For local development, copy `.env.example` to
   `.env`, enter the token there, then load your own file in the shell:

   ```bash
   set -a
   . ./.env
   set +a
   ```

3. Confirm that both configured models have a serving provider. The client
   currently uses the legacy `api-inference.huggingface.co/models/{model}` URL;
   check current HF provider documentation and migrate to the supported route
   before relying on it. A token alone does not establish model availability.
   Dedicated endpoints may require a separate deployment and paid capacity;
   none was provisioned here.
4. Run this check from the repository with the Python environment activated:

   ```bash
   python manage.py shell <<'PY'
   from django.conf import settings
   from apps.nlp.hf_client import score_sentence
   assert settings.HF_API_TOKEN, 'HF_API_TOKEN is missing'
   for model, text in [
       ('finbert', 'Revenue grew and profits improved.'),
       ('xlm-roberta', 'Prestasi kumpulan kukuh dan keuntungan meningkat.'),
   ]:
       result = score_sentence(text, model)
       print(model, result)
       assert result['source'] == 'hf', 'Lexicon fallback is not live inference'
   PY
   ```

Both results must have `source=hf`. An HTTP 200 from `/api/analyze` alone is
insufficient: the application intentionally falls back to the lexicon scorer.

## Bursa

One small announcement-list request was attempted. The workspace proxy refused
the connection (CONNECT 403); this was not a Bursa HTTP response. Listing JSON,
attachment discovery, PDF download and live PDF extraction remain unvalidated.

1. Allow `www.bursamalaysia.com` in the published environment network policy,
   or use a machine with permitted access. The attempted environment grant was
   refused by the published configuration.
2. Fetch a single small page without modifying the database:

   ```bash
   python manage.py shell <<'PY'
   import json
   from pathlib import Path
   from apps.scraper.bursa import fetch_announcements, parse_row
   rows = fetch_announcements(page=1, per_page=1)
   Path('/tmp/bursa-validation.json').write_text(json.dumps(rows))
   print('Rows:', len(rows))
   for row in rows:
       print(parse_row(row))
   PY
   ```

3. Verify the response contains actual quarterly announcements with valid dates,
   company identity and detail URLs. The current implementation assumes JSON
   with a `data` key; HTML or an unexpected schema needs a parser/endpoint fix,
   not repeated requests. An empty list alone does not prove the parser works.
4. Once the listing is confirmed, validate one detail/PDF through
   `resolve_pdf_url`, `download_pdf`, and `extract_narrative`. Confirm that the
   download is a PDF and the extracted text is usable. Reuse recorded responses
   while debugging and preserve the scraper's rate limit.
5. Only after those checks, run `python manage.py scrape_bursa --pages 1 --analyze`
   to exercise database ingestion. This command writes announcements and analysis
   results. The present ingestion code substitutes 1970 for unparseable dates,
   so inspect dates before accepting the output as real financial data.

## Java gateway

Requires a complete JDK 17 or newer and Maven. This repository does not include
a Maven wrapper. The preinstalled Java 21 runtime lacked compiler components
needed for the Java 17 target, so a full Temurin JDK and Maven were installed
under `/workspace/tools` for validation.

In this workspace:

```bash
export JAVA_HOME=/workspace/tools/jdk-21.0.9+10
export PATH=/workspace/tools/apache-maven-3.9.9/bin:$JAVA_HOME/bin:$PATH
export MAVEN_OPTS=-Djavax.net.ssl.trustStore=/etc/ssl/certs/java/cacerts
cd /workspace/earning-analyzer-MY/gateway
mvn -s /workspace/tools/maven-settings.xml -Dmaven.repo.local=/workspace/tools/m2 package
```

On your own machine, install a current JDK 17/21 and Maven, check `javac -version`
and `mvn -v`, then run `mvn package` from `gateway/`. The workspace proxy settings
and truststore above are environment-specific.

Start Django in one terminal from the repository root:

```bash
python manage.py runserver 127.0.0.1:8000 --noreload
```

Start the packaged gateway in another:

```bash
java -jar gateway/target/gateway-0.1.0.jar
```

Check forwarding:

```bash
curl --fail http://localhost:8081/health
curl --fail http://localhost:8081/analyze \
  -H 'Content-Type: application/json' \
  -d '{"text":"Revenue grew 15%. Prestasi kumpulan dijangka kukuh."}'
```

The gateway exposes `/health` and `/analyze`; Django exposes `/api/health` and
`/api/analyze`. The gateway currently forwards requests only: authentication and
rate limiting are not implemented despite the architectural description.
