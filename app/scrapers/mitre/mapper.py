import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.vulnerability import Vulnerability

CVSS_METRIC_KEYS = ("cvssV3_1", "cvssV3_0", "cvssV2_0")


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _extract_description(descriptions: list[dict[str, Any]]) -> str:
    for entry in descriptions:
        if entry.get("lang") == "en":
            return entry.get("value", "")
    return descriptions[0].get("value", "") if descriptions else ""


def _extract_cvss(record: dict[str, Any]) -> tuple[float | None, str | None]:
    containers = record.get("containers", {})
    metric_sources = [containers.get("cna", {}).get("metrics", [])]
    for adp in containers.get("adp", []):
        metric_sources.append(adp.get("metrics", []))

    for metrics in metric_sources:
        for entry in metrics:
            for key in CVSS_METRIC_KEYS:
                cvss_data = entry.get(key)
                if cvss_data:
                    return cvss_data.get("baseScore"), cvss_data.get("baseSeverity")
    return None, None


def _extract_vendor_product(affected: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    for entry in affected:
        vendor = entry.get("vendor")
        product = entry.get("product")
        if vendor and vendor != "n/a":
            return vendor, product
    return None, None


def apply_mitre_enrichment(vulnerability: Vulnerability, record: dict[str, Any]) -> None:
    metadata = record.get("cveMetadata", {})
    vulnerability.cve_state = metadata.get("state")
    vulnerability.assigner_org = metadata.get("assignerShortName")
    vulnerability.date_reserved = _parse_datetime(metadata.get("dateReserved"))


def build_vulnerability_from_mitre(record: dict[str, Any], source_id: uuid.UUID) -> Vulnerability:
    metadata = record.get("cveMetadata", {})
    cna = record.get("containers", {}).get("cna", {})
    cvss_score, severity = _extract_cvss(record)
    affected_vendor, affected_product = _extract_vendor_product(cna.get("affected", []))
    references = [ref.get("url") for ref in cna.get("references", []) if ref.get("url")]

    return Vulnerability(
        cve_id=metadata["cveId"],
        title=cna.get("title") or metadata["cveId"],
        description=_extract_description(cna.get("descriptions", [])),
        severity=severity,
        cvss_score=cvss_score,
        published_date=_parse_datetime(metadata.get("datePublished")),
        updated_date=_parse_datetime(metadata.get("dateUpdated")),
        references=references,
        affected_vendor=affected_vendor,
        affected_product=affected_product,
        source_id=source_id,
        cve_state=metadata.get("state"),
        assigner_org=metadata.get("assignerShortName"),
        date_reserved=_parse_datetime(metadata.get("dateReserved")),
    )
