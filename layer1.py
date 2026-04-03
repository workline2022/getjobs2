"""
Layer 1 orchestrator: scrapes all companies from companies.json
using Greenhouse, Lever, and Ashby ATS APIs.
"""

import json
import logging
import concurrent.futures
from pathlib import Path

from models import Job, Company
from scrapers import greenhouse, lever, ashby
from filters import enrich_jobs

logger = logging.getLogger(__name__)

COMPANIES_FILE = Path(__file__).parent / "companies.json"
MAX_WORKERS = 8


def load_companies(path: Path = COMPANIES_FILE) -> list[Company]:
    data = json.loads(path.read_text())
    return [
        Company(
            name=c["name"],
            ats=c["ats"],
            slug=c["slug"],
            industry=c.get("industry", ""),
        )
        for c in data["companies"]
    ]


def _scrape_company(company: Company) -> list[Job]:
    ats = company.ats.lower()
    if ats == "greenhouse":
        jobs = greenhouse.fetch_jobs(company.name, company.slug, company.industry)
    elif ats == "lever":
        jobs = lever.fetch_jobs(company.name, company.slug, company.industry)
    elif ats == "ashby":
        jobs = ashby.fetch_jobs(company.name, company.slug, company.industry)
    else:
        logger.warning("Unknown ATS '%s' for company %s", ats, company.name)
        jobs = []
    return jobs


def scrape_all(
    companies: list[Company] | None = None,
    max_workers: int = MAX_WORKERS,
) -> list[Job]:
    if companies is None:
        companies = load_companies()

    all_jobs: list[Job] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_scrape_company, c): c for c in companies}
        for future in concurrent.futures.as_completed(futures):
            company = futures[future]
            try:
                jobs = future.result()
                all_jobs.extend(jobs)
            except Exception as e:
                logger.error("Error scraping %s: %s", company.name, e)

    # Deduplicate by hash
    seen: set[str] = set()
    unique: list[Job] = []
    for job in all_jobs:
        key = job.dedup_key()
        if key not in seen:
            seen.add(key)
            unique.append(job)

    logger.info("Layer 1: %d total, %d unique jobs", len(all_jobs), len(unique))
    enrich_jobs(unique)
    return unique
