import uuid

from app.scrapers.nvd.mapper import map_nvd_cve_to_vulnerability

SOURCE_ID = uuid.uuid4()


def _cve_item(**overrides):
    base = {
        "cve": {
            "id": "CVE-2021-44228",
            "published": "2021-12-10T00:00:00.000",
            "lastModified": "2025-10-21T23:25:23.121",
            "descriptions": [
                {"lang": "es", "value": "Descripcion en espanol"},
                {"lang": "en", "value": "Apache Log4j2 JNDI RCE"},
            ],
            "metrics": {
                "cvssMetricV31": [
                    {"cvssData": {"baseScore": 10.0, "baseSeverity": "CRITICAL"}},
                ],
            },
            "affected": [
                {
                    "affectedData": [
                        {"vendor": "Apache Software Foundation", "product": "Apache Log4j2"},
                    ]
                }
            ],
            "references": [{"url": "https://logging.apache.org/log4j/2.x/security.html"}],
        }
    }
    base["cve"].update(overrides)
    return base


def test_prefers_english_description_over_other_languages():
    vulnerability = map_nvd_cve_to_vulnerability(_cve_item(), source_id=SOURCE_ID)
    assert vulnerability.description == "Apache Log4j2 JNDI RCE"


def test_extracts_cvss_v31_score_and_severity():
    vulnerability = map_nvd_cve_to_vulnerability(_cve_item(), source_id=SOURCE_ID)
    assert vulnerability.cvss_score == 10.0
    assert vulnerability.severity == "CRITICAL"


def test_falls_back_to_cvss_v2_when_v3_absent():
    item = _cve_item(
        metrics={
            "cvssMetricV2": [
                {"cvssData": {"baseScore": 7.5}, "baseSeverity": "HIGH"},
            ]
        }
    )
    vulnerability = map_nvd_cve_to_vulnerability(item, source_id=SOURCE_ID)
    assert vulnerability.cvss_score == 7.5
    assert vulnerability.severity == "HIGH"


def test_extracts_vendor_product_from_affected_field():
    vulnerability = map_nvd_cve_to_vulnerability(_cve_item(), source_id=SOURCE_ID)
    assert vulnerability.affected_vendor == "Apache Software Foundation"
    assert vulnerability.affected_product == "Apache Log4j2"


def test_falls_back_to_cpe_match_when_affected_vendor_is_placeholder():
    item = _cve_item(
        affected=[{"affectedData": [{"vendor": "n/a", "product": "n/a"}]}],
        configurations=[
            {
                "nodes": [
                    {
                        "cpeMatch": [
                            {"criteria": "cpe:2.3:a:eric_allman:sendmail:5.58:*:*:*:*:*:*:*"},
                        ]
                    }
                ]
            }
        ],
    )
    vulnerability = map_nvd_cve_to_vulnerability(item, source_id=SOURCE_ID)
    assert vulnerability.affected_vendor == "eric_allman"
    assert vulnerability.affected_product == "sendmail"


def test_parses_naive_dates_as_utc():
    vulnerability = map_nvd_cve_to_vulnerability(_cve_item(), source_id=SOURCE_ID)
    assert vulnerability.published_date.tzinfo is not None
    assert vulnerability.published_date.year == 2021


def test_missing_dates_are_none():
    item = _cve_item(published=None, lastModified=None)
    vulnerability = map_nvd_cve_to_vulnerability(item, source_id=SOURCE_ID)
    assert vulnerability.published_date is None
    assert vulnerability.updated_date is None


def test_title_defaults_to_cve_id():
    vulnerability = map_nvd_cve_to_vulnerability(_cve_item(), source_id=SOURCE_ID)
    assert vulnerability.title == "CVE-2021-44228"


def test_source_id_is_assigned():
    vulnerability = map_nvd_cve_to_vulnerability(_cve_item(), source_id=SOURCE_ID)
    assert vulnerability.source_id == SOURCE_ID
