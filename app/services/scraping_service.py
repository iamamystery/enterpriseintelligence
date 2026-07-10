import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mongodb import get_mongodb
from app.models.source import Source
from app.repositories.mongo.raw_intel_repository import RawIntelRepository
from app.repositories.postgres.source_repository import SourceRepository
from app.repositories.postgres.vulnerability_repository import VulnerabilityRepository
from app.scrapers.cisa.kev_client import CISA_KEV_SOURCE_NAME, CISA_KEV_URL, CISAKEVClient
from app.scrapers.cisa.mapper import apply_kev_enrichment, build_vulnerability_from_kev
from app.scrapers.mitre.client import MITRE_BASE_URL, MITRE_SOURCE_NAME, MITREClient
from app.scrapers.mitre.mapper import apply_mitre_enrichment, build_vulnerability_from_mitre
from app.scrapers.nvd.client import NVDClient
from app.scrapers.nvd.config import NVD_BASE_URL, NVD_SOURCE_NAME
from app.scrapers.nvd.mapper import map_nvd_cve_to_vulnerability
from app.scrapers.vendor_advisories.redhat.mapper import apply_redhat_enrichment, build_vulnerability_from_redhat
from app.scrapers.vendor_advisories.redhat.scraper import REDHAT_BASE_URL, REDHAT_SOURCE_NAME, RedHatClient

logger = logging.getLogger(__name__)


class ScrapingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.sources = SourceRepository(session)
        self.vulnerabilities = VulnerabilityRepository(session)
        self.raw_intel = RawIntelRepository(get_mongodb())

    async def _get_or_create_source(self, name: str, base_url: str) -> Source:
        source = await self.sources.get_by_name(name)
        if source is None:
            source = await self.sources.create(Source(name=name, source_type="api", base_url=base_url))
        return source

    async def ingest_nvd_recent(self, results_per_page: int = 20) -> int:
        source = await self._get_or_create_source(NVD_SOURCE_NAME, NVD_BASE_URL)

        client = NVDClient()
        payload = await client.fetch_recent_cves(results_per_page=results_per_page)

        await self.raw_intel.insert_raw(source=NVD_SOURCE_NAME, payload=payload)

        count = 0
        for item in payload.get("vulnerabilities", []):
            vulnerability = map_nvd_cve_to_vulnerability(item, source_id=source.id)
            await self.vulnerabilities.upsert(vulnerability)
            count += 1

        await self.session.commit()
        logger.info("Ingested %d CVEs from NVD", count)
        return count

    async def ingest_cisa_kev(self, limit: int | None = None) -> int:
        source = await self._get_or_create_source(CISA_KEV_SOURCE_NAME, CISA_KEV_URL)

        client = CISAKEVClient()
        payload = await client.fetch_catalog()

        await self.raw_intel.insert_raw(source=CISA_KEV_SOURCE_NAME, payload=payload)

        entries = payload.get("vulnerabilities", [])
        if limit is not None:
            entries = entries[:limit]

        count = 0
        for item in entries:
            existing = await self.vulnerabilities.get_by_cve_id(item["cveID"])
            if existing is None:
                await self.vulnerabilities.create(build_vulnerability_from_kev(item, source_id=source.id))
            else:
                apply_kev_enrichment(existing, item)
            count += 1

        await self.session.commit()
        logger.info("Ingested %d CISA KEV entries", count)
        return count

    async def ingest_mitre_cves(self, cve_ids: list[str]) -> int:
        source = await self._get_or_create_source(MITRE_SOURCE_NAME, MITRE_BASE_URL)

        client = MITREClient()
        count = 0
        for cve_id in cve_ids:
            record = await client.fetch_cve(cve_id)
            await self.raw_intel.insert_raw(source=MITRE_SOURCE_NAME, payload=record)

            existing = await self.vulnerabilities.get_by_cve_id(cve_id)
            if existing is None:
                await self.vulnerabilities.create(build_vulnerability_from_mitre(record, source_id=source.id))
            else:
                apply_mitre_enrichment(existing, record)
            count += 1

        await self.session.commit()
        logger.info("Processed %d CVEs from MITRE", count)
        return count

    async def ingest_redhat_recent(self, per_page: int = 20) -> int:
        source = await self._get_or_create_source(REDHAT_SOURCE_NAME, REDHAT_BASE_URL)

        client = RedHatClient()
        summary_list = await client.fetch_recent_cves(per_page=per_page)

        await self.raw_intel.insert_raw(source=REDHAT_SOURCE_NAME, payload={"items": summary_list})

        count = 0
        for item in summary_list:
            cve_id = item["CVE"]
            detail = await client.fetch_cve(cve_id)
            if detail is not None:
                await self.raw_intel.insert_raw(source=REDHAT_SOURCE_NAME, payload=detail)
            record = detail or item

            existing = await self.vulnerabilities.get_by_cve_id(cve_id)
            if existing is None:
                await self.vulnerabilities.create(
                    build_vulnerability_from_redhat(record, cve_id=cve_id, source_id=source.id)
                )
            else:
                apply_redhat_enrichment(existing, record)
            count += 1

        await self.session.commit()
        logger.info("Processed %d CVEs from Red Hat", count)
        return count
