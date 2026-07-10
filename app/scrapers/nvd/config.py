from app.core.config import settings

NVD_SOURCE_NAME = "NVD"
NVD_BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
NVD_RESULTS_PER_PAGE = 20


def nvd_headers() -> dict[str, str]:
    if settings.NVD_API_KEY:
        return {"apiKey": settings.NVD_API_KEY}
    return {}
