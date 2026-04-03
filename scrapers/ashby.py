"""
Ashby ATS scraper — uses the public non-user GraphQL endpoint.
Endpoint: https://jobs.ashbyhq.com/api/non-user-graphql
"""

import httpx
import logging
from typing import Optional
from models import Job

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://jobs.ashbyhq.com/api/non-user-graphql"
HEADERS = {
    "User-Agent": "JobSourcingBot/1.0 (research project)",
    "Content-Type": "application/json",
}

JOBS_QUERY = """
query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) {
  jobBoard: jobBoardWithTeams(
    organizationHostedJobsPageName: $organizationHostedJobsPageName
  ) {
    teams {
      id
      name
      parentTeamId
    }
    jobPostings {
      id
      title
      teamId
      locationId
      locationName
      employmentType
      descriptionSocial
      descriptionHtml
      publishedDate
      externalLink
      applyLink
    }
    locationFilters {
      id
      name
    }
  }
}
"""


def fetch_jobs(company_name: str, slug: str, industry: Optional[str] = None) -> list[Job]:
    payload = {
        "operationName": "ApiJobBoardWithTeams",
        "variables": {"organizationHostedJobsPageName": slug},
        "query": JOBS_QUERY,
    }
    try:
        resp = httpx.post(GRAPHQL_URL, json=payload, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.warning("Ashby %s: HTTP %d", slug, e.response.status_code)
        return []
    except httpx.RequestError as e:
        logger.warning("Ashby %s: request error — %s", slug, e)
        return []

    data = resp.json()
    board = (data.get("data") or {}).get("jobBoard") or {}
    postings = board.get("jobPostings", [])

    # Build team id → name lookup
    teams = {t["id"]: t["name"] for t in board.get("teams", [])}

    jobs = []
    for p in postings:
        url = p.get("applyLink") or p.get("externalLink") or f"https://jobs.ashbyhq.com/{slug}/{p.get('id', '')}"
        department = teams.get(p.get("teamId", ""), "")
        description = p.get("descriptionHtml") or p.get("descriptionSocial") or ""
        jobs.append(Job(
            source="ashby",
            company=company_name,
            title=p.get("title", "").strip(),
            location=p.get("locationName", ""),
            url=url,
            job_id=p.get("id", ""),
            description=description,
            industry=industry or "",
            department=department,
        ))
    logger.info("Ashby %s: fetched %d jobs", slug, len(jobs))
    return jobs
