import uuid

from app.models.vulnerability import Vulnerability
from app.scrapers.vendor_advisories.redhat.mapper import (
    apply_redhat_enrichment,
    build_vulnerability_from_redhat,
)

SOURCE_ID = uuid.uuid4()

DETAIL_RECORD = {
    "threat_severity": "Critical",
    "public_date": "2021-12-10T02:01:00Z",
    "cvss3": {"cvss3_base_score": "9.8"},
    "details": ["Full detail description from Red Hat CNA."],
    "statement": "This issue only affects log4j versions between 2.0 and 2.14.1.",
}

SUMMARY_ITEM = {
    "CVE": "CVE-2026-54499",
    "severity": "important",
    "public_date": "2026-07-08T22:23:02Z",
    "bugzilla_description": "stanza: Remote Code Execution via unsafe deserialization",
    "cvss3_score": "7.5",
}


def test_build_from_detail_record_extracts_statement_and_cvss():
    vulnerability = build_vulnerability_from_redhat(DETAIL_RECORD, cve_id="CVE-2021-44228", source_id=SOURCE_ID)
    assert vulnerability.redhat_severity == "Critical"
    assert vulnerability.redhat_statement == "This issue only affects log4j versions between 2.0 and 2.14.1."
    assert vulnerability.cvss_score == 9.8
    assert vulnerability.description == "Full detail description from Red Hat CNA."


def test_build_from_bulk_summary_shape_has_no_statement():
    vulnerability = build_vulnerability_from_redhat(SUMMARY_ITEM, cve_id="CVE-2026-54499", source_id=SOURCE_ID)
    assert vulnerability.redhat_severity == "important"
    assert vulnerability.redhat_statement is None
    assert vulnerability.cvss_score == 7.5
    assert vulnerability.description == "stanza: Remote Code Execution via unsafe deserialization"


def test_enrichment_never_overwrites_existing_descriptive_fields():
    existing = Vulnerability(
        cve_id="CVE-2021-44228",
        title="Original title from NVD",
        description="Original description from NVD",
        severity="CRITICAL",
        cvss_score=10.0,
        affected_vendor="Apache Software Foundation",
        source_id=SOURCE_ID,
    )

    apply_redhat_enrichment(existing, DETAIL_RECORD)

    assert existing.title == "Original title from NVD"
    assert existing.description == "Original description from NVD"
    assert existing.severity == "CRITICAL"
    assert existing.cvss_score == 10.0

    assert existing.redhat_severity == "Critical"
    assert existing.redhat_statement == DETAIL_RECORD["statement"]


def test_enrichment_does_not_clear_statement_when_record_lacks_one():
    existing = Vulnerability(
        cve_id="CVE-2026-54499",
        title="t",
        description="d",
        redhat_statement="previously captured statement",
        source_id=SOURCE_ID,
    )

    apply_redhat_enrichment(existing, SUMMARY_ITEM)

    assert existing.redhat_statement == "previously captured statement"
