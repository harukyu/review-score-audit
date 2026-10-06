"""Offline arithmetic and data-quality checks for manually recorded review scores."""

from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

VERSION = "0.1.0"
MAX_BYTES = 1024 * 1024
MAX_SOURCES = 500
MAX_COUNT = 1_000_000_000


class InputError(ValueError):
    """Invalid data; error messages never include the original values."""


def decimal_value(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal, float)):
        raise InputError("Rating and scale values must be decimal numbers or strings.")
    text = str(value)
    if len(text) > 32 or not re.fullmatch(r"-?\d{1,9}(?:\.\d{1,12})?", text):
        raise InputError("Decimals use plain notation, at most 9 integer and 12 fractional digits.")
    try:
        result = Decimal(text)
    except InvalidOperation as exc:
        raise InputError("A decimal is invalid.") from exc
    if not result.is_finite():
        raise InputError("All decimals must be finite.")
    return result


def iso_date(value: object) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise InputError("Dates must use YYYY-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise InputError("A calendar date is invalid.") from exc


def source_url(value: object) -> str:
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 or ord(c) == 127 for c in value):
        raise InputError("Source URL must be a bounded HTTP(S) URL without whitespace.")
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username is not None or parsed.password is not None):
            raise InputError("Source URL must be HTTP(S), with a host and no credentials.")
        port = parsed.port
        host = parsed.hostname.encode("idna").decode("ascii").lower()
    except (ValueError, UnicodeError) as exc:
        raise InputError("A source URL cannot be parsed.") from exc
    # Used only for duplicate-source detection. Never fetched.
    return f"{host}:{port or (443 if parsed.scheme == 'https' else 80)}{parsed.path.rstrip('/')}?{parsed.query}"


def analyze(document: object, *, as_of: date | None = None, max_age_days: int = 90,
            allow_mixed_scales: bool = False) -> dict:
    if type(max_age_days) is not int or not 0 <= max_age_days <= 36500 or type(allow_mixed_scales) is not bool:
        raise InputError("Invalid age limit or mixed-scale option.")
    as_of = as_of or date.today()
    if type(as_of) is not date:
        raise InputError("as_of must be a date.")
    if not isinstance(document, dict) or set(document) - {"schema_version", "sources"}:
        raise InputError("Input must be an object using only schema_version and sources.")
    if type(document.get("schema_version")) is not int or document["schema_version"] != 1:
        raise InputError("schema_version must be integer 1.")
    sources = document.get("sources")
    if not isinstance(sources, list) or not 1 <= len(sources) <= MAX_SOURCES:
        raise InputError("sources must contain 1–500 source objects.")
    report = {
        "schema_version": 1, "analyzer_version": VERSION, "complete": True,
        "as_of": as_of.isoformat(), "method": "count_weighted_mean_of_recorded_source_averages",
        "target_scale": {"min": "1", "max": "5"},
        "summary": {"source_count": len(sources), "included_sources": 0,
                    "recorded_review_count_sum": 0, "score": None, "errors": 0, "warnings": 0},
        "sources": [], "issues": [],
        "limitations": [
            "Source averages may already be rounded; the pooled result is approximate.",
            "Summed source counts are not a count of unique people or deduplicated reviews.",
            "Values and dates are user supplied; no platform is contacted or verified.",
            "Linear scale conversion does not prove that rating systems are comparable.",
        ],
    }

    def issue(code: str, severity: str, message: str, identifier: str = "") -> None:
        report["issues"].append({"code": code, "severity": severity, "message": message, "source_id": identifier})
        report["summary"]["errors" if severity == "error" else "warnings"] += 1

    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    included: list[tuple[Decimal, int]] = []
    scales: set[tuple[Decimal, Decimal]] = set()
    with localcontext() as context:
        context.prec = 50
        for source in sources:
            permitted = {"id", "rating", "count", "scale_min", "scale_max", "updated_at", "url"}
            if not isinstance(source, dict) or set(source) - permitted:
                raise InputError("Every source must use only documented keys.")
            identifier = source.get("id")
            if not isinstance(identifier, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", identifier):
                raise InputError("Each source id uses 1–64 lowercase ASCII letters, digits, underscores, or hyphens.")
            if identifier in seen_ids:
                raise InputError("Source ids must be unique.")
            seen_ids.add(identifier)
            count = source.get("count")
            if type(count) is not int or not 0 <= count <= MAX_COUNT:
                raise InputError("Review counts must be integers between 0 and 1,000,000,000.")
            minimum = decimal_value(source.get("scale_min", "1"))
            maximum = decimal_value(source.get("scale_max", "5"))
            if not Decimal("0") <= minimum < maximum <= Decimal("100"):
                raise InputError("Scale bounds must satisfy 0 <= min < max <= 100.")
            rating = None if source.get("rating") is None else decimal_value(source["rating"])
            if count and rating is None:
                raise InputError("A source with reviews requires a rating.")
            if rating is not None and not minimum <= rating <= maximum:
                raise InputError("A rating falls outside its source scale.")
            updated = None if source.get("updated_at") is None else iso_date(source["updated_at"])
            if updated is None:
                issue("missing_date", "warning", "No recorded data date is available.", identifier)
            elif updated > as_of:
                issue("future_date", "error", "Recorded data date is after the report date.", identifier)
            elif (as_of - updated).days > max_age_days:
                issue("stale_source", "warning", "Recorded data is older than the chosen age limit.", identifier)
            url_key = None if source.get("url") is None else source_url(source["url"])
            if url_key is None:
                issue("missing_source_link", "warning", "No source profile URL was recorded.", identifier)
            elif url_key in seen_urls:
                issue("duplicate_source_link", "error", "More than one source points to the same profile URL.", identifier)
            else:
                seen_urls.add(url_key)
            normalized = None
            if count and rating is not None:
                normalized = Decimal("1") + (rating - minimum) * Decimal("4") / (maximum - minimum)
                included.append((normalized, count))
                scales.add((minimum, maximum))
            else:
                issue("zero_weight_source", "warning", "Zero-review source is excluded from the weighted score.", identifier)
            report["sources"].append({
                "id": identifier, "count": count, "rating": str(rating) if rating is not None else None,
                "scale_min": str(minimum), "scale_max": str(maximum),
                "normalized_rating": str(normalized.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)) if normalized is not None else None,
                "updated_at": updated.isoformat() if updated else None, "has_source_link": url_key is not None,
            })
        if len(scales) > 1 or (scales and scales != {(Decimal("1"), Decimal("5"))}):
            issue("scale_conversion", "warning" if allow_mixed_scales else "error",
                  "Source scales require linear conversion to 1–5; explicit opt-in is required.")
        total = sum(count for _, count in included)
        report["summary"].update(included_sources=len(included), recorded_review_count_sum=total)
        if not total:
            issue("no_weighted_data", "error", "No positive review count is available for a score.")
        if total and not report["summary"]["errors"]:
            weighted = sum((rating * count for rating, count in included), Decimal("0")) / total
            report["summary"]["score"] = str(weighted.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            for result in report["sources"]:
                result["weight_percent"] = str((Decimal(result["count"]) * 100 / total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return report


def load_json(raw: bytes) -> object:
    def pairs(items: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in items:
            if key in result:
                raise InputError("Repeated JSON object keys are not allowed.")
            result[key] = value
        return result
    def bad_constant(_: str) -> None:
        raise InputError("Non-finite JSON numbers are not allowed.")
    try:
        return json.loads(raw, parse_float=Decimal, parse_constant=bad_constant, object_pairs_hook=pairs)
    except (ValueError, UnicodeError, RecursionError, InvalidOperation) as exc:
        raise InputError("Input is not valid bounded decimal JSON with unique keys.") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Source JSON, or - for stdin")
    parser.add_argument("--as-of", help="Fixed report date YYYY-MM-DD; defaults to local date")
    parser.add_argument("--max-age-days", type=int, default=90)
    parser.add_argument("--allow-mixed-scales", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--fail-on", choices=("error", "warning", "none"), default="error")
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args(argv)
    try:
        if args.input == "-":
            raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        else:
            with Path(args.input).open("rb") as stream:
                raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise InputError("Input exceeds 1 MiB.")
        report = analyze(load_json(raw), as_of=iso_date(args.as_of) if args.as_of else None,
                         max_age_days=args.max_age_days, allow_mixed_scales=args.allow_mixed_scales)
    except (OSError, InputError):
        print("Input error: cannot read input, or data/options are invalid. Original values are omitted.", file=sys.stderr)
        return 3
    if args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=True))
    else:
        s = report["summary"]
        print(f"Review Score Audit {VERSION}: {s['score'] or 'unavailable'} / 5")
        print(f"Recorded review count sum: {s['recorded_review_count_sum']}; included sources: {s['included_sources']}")
        print(f"Errors: {s['errors']}; warnings: {s['warnings']}")
        for finding in report["issues"]:
            print(f"{finding['severity'].upper()} {finding['code']} {finding['source_id']}: {finding['message']}")
        print("Source counts may overlap; this does not verify reviews or unique reviewers.")
    if args.fail_on != "none" and report["summary"]["errors"]:
        return 2
    return 1 if args.fail_on == "warning" and report["summary"]["warnings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
