import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.vulnerability import Vulnerability

CVSS_METRIC_KEYS = ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2")


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _extract_description(descriptions: list[dict[str, Any]]) -> str:
    for entry in descriptions:
        if entry.get("lang") == "en":
            return entry.get("value", "")
    return descriptions[0].get("value", "") if descriptions else ""


def _extract_cvss(metrics: dict[str, Any]) -> tuple[float | None, str | None]:
    for key in CVSS_METRIC_KEYS:
        entries = metrics.get(key)
        if entries:
            cvss_data = entries[0].get("cvssData", {})
            score = cvss_data.get("baseScore")
            severity = cvss_data.get("baseSeverity") or entries[0].get("baseSeverity")
            return score, severity
    return None, None


def _extract_vendor_product(cve: dict[str, Any]) -> tuple[str | None, str | None]:
    for affected in cve.get("affected", []):
        for affected_data in affected.get("affectedData", []):
            vendor = affected_data.get("vendor")
            product = affected_data.get("product")
            if vendor and vendor != "n/a":
                return vendor, product

    for config in cve.get("configurations", []):
        for node in config.get("nodes", []):
            for cpe_match in node.get("cpeMatch", []):
                parts = cpe_match.get("criteria", "").split(":")
                if len(parts) > 4 and parts[3] != "*":
                    return parts[3] or None, parts[4] or None

    return None, None


def map_nvd_cve_to_vulnerability(cve_item: dict[str, Any], source_id: uuid.UUID) -> Vulnerability:
    cve = cve_item["cve"]
    cvss_score, severity = _extract_cvss(cve.get("metrics", {}))
    affected_vendor, affected_product = _extract_vendor_product(cve)
    references = [ref.get("url") for ref in cve.get("references", []) if ref.get("url")]

    return Vulnerability(
        cve_id=cve["id"],
        title=cve["id"],
        description=_extract_description(cve.get("descriptions", [])),
        severity=severity,
        cvss_score=cvss_score,
        published_date=_parse_datetime(cve.get("published")),
        updated_date=_parse_datetime(cve.get("lastModified")),
        references=references,
        affected_vendor=affected_vendor,
        affected_product=affected_product,
        source_id=source_id,
    )
