import uuid
from datetime import date, datetime
from typing import Any

from app.models.vulnerability import Vulnerability


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def build_vulnerability_from_kev(item: dict[str, Any], source_id: uuid.UUID) -> Vulnerability:
    return Vulnerability(
        cve_id=item["cveID"],
        title=item.get("vulnerabilityName", item["cveID"]),
        description=item.get("shortDescription", ""),
        affected_vendor=item.get("vendorProject"),
        affected_product=item.get("product"),
        references=[],
        source_id=source_id,
        is_known_exploited=True,
        kev_date_added=_parse_date(item.get("dateAdded")),
        kev_due_date=_parse_date(item.get("dueDate")),
        ransomware_campaign_use=item.get("knownRansomwareCampaignUse"),
    )


def apply_kev_enrichment(vulnerability: Vulnerability, item: dict[str, Any]) -> None:
    vulnerability.is_known_exploited = True
    vulnerability.kev_date_added = _parse_date(item.get("dateAdded"))
    vulnerability.kev_due_date = _parse_date(item.get("dueDate"))
    vulnerability.ransomware_campaign_use = item.get("knownRansomwareCampaignUse")
