"""
Lever ATS scraper — uses the public v0 postings JSON API.
Endpoint: https://api.lever.co/v0/postings/{slug}
"""

import httpx
import logging
from typing import Optional
from models import Job

logger = logging.getLogger(__name__)

BASE_URL = "https://api.lever.co/v0/postings/{slug}"
HEADERS = {"User-Agent": "JobSourcingBot/1.0 (research project)"}


def fetch_jobs(company_name: str, slug: str, industry: Optional[str] = None) -> list[Job]:
    url = BASE_URL.format(slug=slug)
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=15, params={"mode": "json"})
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.warning("Lever %s: HTTP %d", slug, e.response.status_code)
        return []
    except httpx.RequestError as e:
        logger.warning("Lever %s: request error — %s", slug, e)
        return []

    raw_jobs = resp.json()
    if not isinstance(raw_jobs, list):
        logger.warning("Lever %s: unexpected response format", slug)
        return []

    jobs = []
    for j in raw_jobs:
        description = _extract_description(j)
        jobs.append(Job(
            source="lever",
            company=company_name,
            title=j.get("text", "").strip(),
            location=j.get("categories", {}).get("location", ""),
            url=j.get("hostedUrl", "") or j.get("applyUrl", ""),
            job_id=j.get("id", ""),
            description=description,
            industry=industry or "",
            department=j.get("categories", {}).get("department", ""),
        ))
    logger.info("Lever %s: fetched %d jobs", slug, len(jobs))
    return jobs


def _extract_description(j: dict) -> str:
    parts = []
    desc_body = j.get("descriptionBody", "") or j.get("description", "")
    if desc_body:
        parts.append(desc_body)
    for section in j.get("lists", []):
        parts.append(section.get("text", ""))
        for item in section.get("content", []):
            parts.append(item)
    for addon in j.get("additional", []):
        parts.append(addon.get("text", ""))
    return " ".join(parts)
