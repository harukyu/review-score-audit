# Review Score Audit

[![Syntax and packaging](https://github.com/harukyu/review-score-audit/actions/workflows/ci.yml/badge.svg)](https://github.com/harukyu/review-score-audit/actions/workflows/ci.yml)

**Explain the arithmetic behind a combined review score.** Audit manually recorded platform averages, review counts, data dates, and scale choices before presenting a summary on a website.

Independently built by [Nakaryu GmbH](https://nakaryu.de). Runs offline with Python **3.10+** and its standard library. No WordPress plugin, platform API, scraper, or third-party package is needed.

> Version 0.1.0 is a developer preview. It checks supplied arithmetic and metadata. It does not verify genuine reviews, independent reviewers, platform permissions, or eligibility for search-engine rich results.

[Deutsche Anleitung](docs/DE.md) · [Download](https://github.com/harukyu/review-score-audit/releases/tag/v0.1.0) · [Example report](examples/reports/sources.json)

## Quick start

Download and extract the source ZIP, or clone this repository:

```sh
python3 review_score_audit.py examples/sources.json --as-of=2026-10-06
python3 review_score_audit.py examples/sources.json --as-of=2026-10-06 --format=json
python3 review_score_audit.py examples/needs-review.json --as-of=2026-10-06 --format=json
```

The first synthetic fixture has 120 recorded reviews at 4.8 and 30 at 4.2, both on a 1–5 scale:

```text
(4.8 × 120 + 4.2 × 30) / 150 = 4.68
```

The source weights are 80% and 20%. A plain mean of the two averages would give a different result. This tool reports the count-weighted mean and its inputs explicitly.

## Input

```json
{
  "schema_version": 1,
  "sources": [
    {
      "id": "platform-a",
      "rating": "4.8",
      "count": 120,
      "scale_min": "1",
      "scale_max": "5",
      "updated_at": "2026-10-06",
      "url": "https://reviews.example.test/profile-a"
    }
  ]
}
```

| Field | Rule |
| --- | --- |
| `id` | Unique, 1–64 lowercase ASCII letters/digits/underscore/hyphen, beginning with a letter or digit. |
| `rating` | Finite decimal within the source scale; required when `count` is positive. |
| `count` | Integer 0–1,000,000,000. Zero-weight sources are excluded. |
| `scale_min`, `scale_max` | Default 1 and 5. Bounds must satisfy 0 ≤ min < max ≤ 100. |
| `updated_at` | Optional YYYY-MM-DD; missing, stale, and future dates are reported. |
| `url` | Optional HTTP(S) source URL without credentials; never fetched or copied into the report. |

Only documented fields are accepted. Duplicate JSON object keys and source IDs are rejected. Use plain decimal strings for predictable precision; up to 9 integer and 12 fractional digits are supported. Scientific notation in strings is rejected. JSON decimal numbers are parsed using `Decimal`.

Input has its own documented schema. An export from a commercial review plugin may need an explicit local mapping; this is not a drop-in importer for any particular plugin.

## What the audit reports

| Finding | Level | Result |
| --- | --- | --- |
| `missing_date` | Warning | A source has no recorded data date. |
| `stale_source` | Warning | Data is older than `--max-age-days` (default 90). |
| `future_date` | Error | Date is later than the chosen report date. |
| `missing_source_link` | Warning | No source profile URL was supplied. |
| `duplicate_source_link` | Error | Multiple source entries point to the same normalized profile URL. |
| `zero_weight_source` | Warning | A zero-review source contributes no weight. |
| `scale_conversion` | Error by default | At least one contributing source requires conversion to the target 1–5 scale. |
| `no_weighted_data` | Error | There are no positive review counts. |

The score is withheld whenever an error is present. Warnings remain visible with the arithmetic, rather than silently removing stale or undated sources.

Source URLs are compared by normalized host, effective port, path without its trailing slash, and query; fragments are ignored. This is a basic duplicate check. Redirects, alternate hostnames, trackers, and repeated reviewers across platforms are not resolved.

## Different scales need an explicit decision

If a source has a 0–10 or 0–5 scale, the tool will require `--allow-mixed-scales` before producing a 1–5 summary:

```sh
python3 review_score_audit.py examples/needs-review.json --as-of=2026-10-06 --allow-mixed-scales
```

Conversion is linear:

```text
normalized = 1 + (rating − source_min) × 4 / (source_max − source_min)
```

A score of 8.5 on 0–10 therefore becomes 4.4 on 1–5. This formula is a modeling choice. It does not establish that different platforms measure the same thing. Define each source's actual scale; do not assume every five-star platform uses the same lower bound.

## Reports and exit codes

JSON schema version 1 includes the report date, method, target scale, source inputs, six-decimal normalized source scores, two-decimal display score, weights, findings, and explicit limitations. The weighted calculation uses full working precision, not the rounded normalized values in the report. Display rounding uses `ROUND_HALF_UP`.

`recorded_review_count_sum` is deliberately a sum of supplied platform counts. It is **not a count of unique people**. Source averages may already be rounded, so the combined score is an approximation even though the arithmetic uses decimal numbers. Weight percentages can sum to 99.99% or 100.01% after display rounding.

Exit codes: 0 no selected failure; 1 warnings with `--fail-on=warning`; 2 report errors; 3 input/options file error. Argument syntax errors use argparse's standard exit 2. `--fail-on=none` returns informational reports even when the score is withheld.

For Python use:

```python
from datetime import date
from review_score_audit import analyze

report = analyze(source_document, as_of=date(2026, 10, 6))
```

`analyze` raises `InputError` for an invalid document. The CLI reads at most 1 MiB; the analyzer accepts up to 500 sources. Reports omit profile URLs but include source IDs, scores, counts, and dates supplied by the operator. No review texts or personal identifiers are needed.

## Development and limits

```sh
python3 -m compileall -q review_score_audit.py tools
python3 tools/package.py
```

GitHub Actions performs syntax compilation and allowlist-based packaging on Python 3.10, 3.12, and 3.14. These are not a behavioral validation suite. Example reports are synthetic demonstrations. No live review platform, paid-plugin integration, or eligibility for structured-data markup has been checked.

No network requests, automatic scraping, review-widget rendering, or JSON-LD output are implemented. Use the report to review your calculation and data choices. The arithmetic relies on Python's documented [Decimal](https://docs.python.org/3/library/decimal.html) implementation.

MIT licensed, copyright 2026 Nakaryu GmbH. All examples are synthetic. No commercial plugin implementation or customer data is included.

Related: [WP Shortcode Audit](https://github.com/harukyu/wp-shortcode-audit) · [Email Recipient Audit](https://github.com/harukyu/email-recipient-audit).
