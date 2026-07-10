import uuid

from app.models.vulnerability import Vulnerability
from app.scrapers.mitre.mapper import apply_mitre_enrichment, build_vulnerability_from_mitre

SOURCE_ID = uuid.uuid4()


def _record(**overrides):
    base = {
        "cveMetadata": {
            "cveId": "CVE-2021-44228",
            "state": "PUBLISHED",
            "assignerShortName": "apache",
            "datePublished": "2021-12-10T00:00:00.000Z",
            "dateUpdated": "2025-10-21T23:25:23.121Z",
            "dateReserved": "2021-11-26T00:00:00.000Z",
        },
        "containers": {
            "cna": {
                "title": "Apache Log4j2 JNDI RCE",
                "descriptions": [{"lang": "en", "value": "Apache Log4j2 JNDI RCE description"}],
                "affected": [{"vendor": "Apache Software Foundation", "product": "Apache Log4j2"}],
                "references": [{"url": "https://logging.apache.org/log4j/2.x/security.html"}],
                "metrics": [{"other": {"type": "unknown", "content": {"other": "critical"}}}],
            },
            "adp": [
                {
                    "providerMetadata": {"shortName": "CISA-ADP"},
                    "metrics": [{"cvssV3_1": {"baseScore": 10.0, "baseSeverity": "CRITICAL"}}],
                }
            ],
        },
    }
    base["cveMetadata"].update(overrides.pop("cveMetadata", {}))
    return base


def test_build_from_mitre_uses_adp_cvss_when_cna_has_no_structured_metrics():
    record = _record()
    vulnerability = build_vulnerability_from_mitre(record, source_id=SOURCE_ID)
    assert vulnerability.cvss_score == 10.0
    assert vulnerability.severity == "CRITICAL"


def test_build_from_mitre_prefers_cna_cvss_when_present():
    record = _record()
    record["containers"]["cna"]["metrics"] = [
        {"cvssV3_1": {"baseScore": 7.5, "baseSeverity": "HIGH"}}
    ]
    vulnerability = build_vulnerability_from_mitre(record, source_id=SOURCE_ID)
    assert vulnerability.cvss_score == 7.5
    assert vulnerability.severity == "HIGH"


def test_build_from_mitre_sets_metadata_fields():
    vulnerability = build_vulnerability_from_mitre(_record(), source_id=SOURCE_ID)
    assert vulnerability.cve_state == "PUBLISHED"
    assert vulnerability.assigner_org == "apache"
    assert vulnerability.date_reserved.year == 2021
    assert vulnerability.affected_vendor == "Apache Software Foundation"


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

    record = _record()
    record["containers"]["cna"]["title"] = "SHOULD-NOT-OVERWRITE"
    record["containers"]["cna"]["descriptions"] = [{"lang": "en", "value": "SHOULD-NOT-OVERWRITE"}]

    apply_mitre_enrichment(existing, record)

    assert existing.title == "Original title from NVD"
    assert existing.description == "Original description from NVD"
    assert existing.severity == "CRITICAL"
    assert existing.cvss_score == 10.0

    assert existing.cve_state == "PUBLISHED"
    assert existing.assigner_org == "apache"
