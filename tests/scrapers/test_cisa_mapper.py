import uuid

from app.models.vulnerability import Vulnerability
from app.scrapers.cisa.mapper import apply_kev_enrichment, build_vulnerability_from_kev

SOURCE_ID = uuid.uuid4()

KEV_ITEM = {
    "cveID": "CVE-2026-48908",
    "vendorProject": "JoomShaper",
    "product": "SP Page Builder",
    "vulnerabilityName": "JoomShaper SP Page Builder Unrestricted Upload Vulnerability",
    "dateAdded": "2026-07-07",
    "shortDescription": "Allows unauthenticated file upload leading to RCE.",
    "dueDate": "2026-07-10",
    "knownRansomwareCampaignUse": "Unknown",
}


def test_build_from_kev_sets_exploitation_flags():
    vulnerability = build_vulnerability_from_kev(KEV_ITEM, source_id=SOURCE_ID)
    assert vulnerability.cve_id == "CVE-2026-48908"
    assert vulnerability.is_known_exploited is True
    assert vulnerability.kev_date_added.isoformat() == "2026-07-07"
    assert vulnerability.kev_due_date.isoformat() == "2026-07-10"
    assert vulnerability.ransomware_campaign_use == "Unknown"
    assert vulnerability.affected_vendor == "JoomShaper"


def test_enrichment_never_overwrites_existing_descriptive_fields():
    existing = Vulnerability(
        cve_id="CVE-1999-0095",
        title="The debug command in Sendmail is enabled",
        description="Original NVD description",
        severity="HIGH",
        cvss_score=10.0,
        affected_vendor="eric_allman",
        affected_product="sendmail",
        source_id=SOURCE_ID,
    )

    fake_kev_item = {
        "cveID": "CVE-1999-0095",
        "vendorProject": "SHOULD-NOT-APPEAR",
        "product": "SHOULD-NOT-APPEAR",
        "vulnerabilityName": "SHOULD-NOT-OVERWRITE-TITLE",
        "shortDescription": "SHOULD-NOT-OVERWRITE-DESCRIPTION",
        "dateAdded": "2026-01-01",
        "dueDate": "2026-01-15",
        "knownRansomwareCampaignUse": "Known",
    }

    apply_kev_enrichment(existing, fake_kev_item)

    assert existing.title == "The debug command in Sendmail is enabled"
    assert existing.description == "Original NVD description"
    assert existing.severity == "HIGH"
    assert existing.cvss_score == 10.0
    assert existing.affected_vendor == "eric_allman"
    assert existing.affected_product == "sendmail"

    assert existing.is_known_exploited is True
    assert existing.kev_date_added.isoformat() == "2026-01-01"
    assert existing.ransomware_campaign_use == "Known"


def test_missing_dates_are_none():
    item = {**KEV_ITEM, "dateAdded": None, "dueDate": None}
    vulnerability = build_vulnerability_from_kev(item, source_id=SOURCE_ID)
    assert vulnerability.kev_date_added is None
    assert vulnerability.kev_due_date is None
