"""
Layer 2 orchestrator: uses python-jobspy to scrape Indeed and Google Jobs,
then deduplicates against Layer 1 results.
"""

import logging
from models import Job
from filters import enrich_jobs

logger = logging.getLogger(__name__)


def scrape_jobspy(
    query: str = "software engineer",
    location: str = "United States",
    results_wanted: int = 50,
    existing_keys: set[str] | None = None,
) -> list[Job]:
    """
    Scrape Indeed and Google Jobs via JobSpy.
    `existing_keys` is the set of dedup hashes already in Layer 1.
    Returns only new (non-duplicate) jobs.
    """
    try:
        from jobspy import scrape_jobs  # type: ignore
    except ImportError:
        logger.error("python-jobspy not installed. Run: pip install python-jobspy")
        return []

    try:
        df = scrape_jobs(
            site_name=["indeed", "google"],
            search_term=query,
            location=location,
            results_wanted=results_wanted,
            hours_old=72,
        )
    except Exception as e:
        logger.error("JobSpy scrape failed: %s", e)
        return []

    jobs: list[Job] = []
    for _, row in df.iterrows():
        job = Job(
            source=str(row.get("site", "jobspy")).lower(),
            company=str(row.get("company", "") or ""),
            title=str(row.get("title", "") or ""),
            location=str(row.get("location", "") or ""),
            url=str(row.get("job_url", "") or ""),
            job_id=str(row.get("id", "") or ""),
            description=str(row.get("description", "") or ""),
            industry="",
            department="",
        )
        jobs.append(job)

    enrich_jobs(jobs)

    if existing_keys:
        before = len(jobs)
        jobs = [j for j in jobs if j.dedup_key() not in existing_keys]
        logger.info("JobSpy: %d total, %d new after dedup", before, len(jobs))
    else:
        logger.info("JobSpy: %d jobs fetched", len(jobs))

    return jobs
