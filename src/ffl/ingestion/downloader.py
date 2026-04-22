import logging
import tempfile
from pathlib import Path

import httpx

from ffl.config import settings

logger = logging.getLogger(__name__)

# ATF publishes separate state-level files and a national file.
# The national file URL may change; also try the direct listing page.
ATF_NATIONAL_URL = settings.atf_data_url

# Fallback: known direct URL pattern for the national FFL listing text file
ATF_FALLBACK_URLS = [
    "https://www.atf.gov/firearms/docs/undefined/ffllisting_0txt/download",
    "https://www.atf.gov/firearms/docs/report/federal-firearms-licensees-ffl-listing/download",
]


async def download_atf_data(url: str | None = None) -> Path:
    """Download ATF FFL text file to a temp file, return its path."""
    urls = [url] if url else [ATF_NATIONAL_URL] + ATF_FALLBACK_URLS

    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        for attempt_url in urls:
            logger.info("Downloading ATF data from %s", attempt_url)
            try:
                resp = await client.get(attempt_url)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.warning("HTTP %s from %s, trying next URL", exc.response.status_code, attempt_url)
                continue
            except httpx.RequestError as exc:
                logger.warning("Request error from %s: %s", attempt_url, exc)
                continue

            tmp = tempfile.NamedTemporaryFile(
                suffix=".txt", delete=False, prefix="atf_ffl_"
            )
            tmp.write(resp.content)
            tmp.close()
            logger.info("Downloaded %d bytes to %s", len(resp.content), tmp.name)
            return Path(tmp.name)

    raise RuntimeError("Failed to download ATF data from all known URLs")
