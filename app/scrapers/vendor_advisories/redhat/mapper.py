import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.vulnerability import Vulnerability


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _extract_severity(record: dict[str, Any]) -> str | None:
    return record.get("threat_severity") or record.get("severity")


def _extract_cvss_score(record: dict[str, Any]) -> float | None:
    cvss3 = record.get("cvss3") or {}
    score = cvss3.get("cvss3_base_score") or record.get("cvss3_score")
    try:
        return float(score) if score not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _extract_description(record: dict[str, Any]) -> str:
    details = record.get("details") or []
    if details:
        return details[0]
    return record.get("bugzilla_description", "")


def apply_redhat_enrichment(vulnerability: Vulnerability, record: dict[str, Any]) -> None:
    vulnerability.redhat_severity = _extract_severity(record)
    statement = record.get("statement")
    if statement:
        vulnerability.redhat_statement = statement


def build_vulnerability_from_redhat(record: dict[str, Any], cve_id: str, source_id: uuid.UUID) -> Vulnerability:
    return Vulnerability(
        cve_id=cve_id,
        title=cve_id,
        description=_extract_description(record),
        cvss_score=_extract_cvss_score(record),
        published_date=_parse_datetime(record.get("public_date")),
        references=[],
        source_id=source_id,
        redhat_severity=_extract_severity(record),
        redhat_statement=record.get("statement"),
    )
