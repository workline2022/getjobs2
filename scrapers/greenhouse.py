"""
Greenhouse ATS scraper — uses the public boards JSON API.
Endpoint: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs
"""

import httpx
import logging
from typing import Optional
from models import Job

logger = logging.getLogger(__name__)

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
HEADERS = {"User-Agent": "JobSourcingBot/1.0 (research project)"}


def fetch_jobs(company_name: str, slug: str, industry: Optional[str] = None) -> list[Job]:
    url = BASE_URL.format(slug=slug)
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=15, params={"content": "true"})
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.warning("Greenhouse %s: HTTP %d", slug, e.response.status_code)
        return []
    except httpx.RequestError as e:
        logger.warning("Greenhouse %s: request error — %s", slug, e)
        return []

    data = resp.json()
    raw_jobs = data.get("jobs", [])
    jobs = []
    for j in raw_jobs:
        location = _extract_location(j)
        jobs.append(Job(
            source="greenhouse",
            company=company_name,
            title=j.get("title", "").strip(),
            location=location,
            url=j.get("absolute_url", ""),
            job_id=str(j.get("id", "")),
            description=j.get("content", ""),
            industry=industry or "",
            department=_extract_department(j),
        ))
    logger.info("Greenhouse %s: fetched %d jobs", slug, len(jobs))
    return jobs


def _extract_location(j: dict) -> str:
    loc = j.get("location", {})
    if isinstance(loc, dict):
        return loc.get("name", "")
    if isinstance(loc, str):
        return loc
    # Some listings have offices array
    offices = j.get("offices", [])
    if offices:
        return offices[0].get("name", "")
    return ""


def _extract_department(j: dict) -> str:
    departments = j.get("departments", [])
    if departments:
        return departments[0].get("name", "")
    return ""
