"""
FastAPI server for the Job Sourcing Platform.

Run with:
    uvicorn api:app --reload

Endpoints:
    GET /jobs?state=NY&industry=healthcare&company=acme&limit=50&offset=0
    GET /stats
    POST /scrape              — trigger a full scrape (background task)
    POST /scrape?layer1_only=true
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.responses import JSONResponse

import database
import layer1
import layer2
from models import Job

logger = logging.getLogger(__name__)

# Track running scrape state (simple in-process flag)
_scrape_running = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield


app = FastAPI(
    title="Job Sourcing Platform",
    description="Aggregates job postings from Greenhouse, Lever, Ashby (Layer 1) and JobSpy (Layer 2).",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# GET /jobs
# ---------------------------------------------------------------------------

@app.get("/jobs", summary="Query stored jobs")
def get_jobs(
    state: Optional[str] = Query(None, description="US state code, e.g. CA or NY"),
    industry: Optional[str] = Query(None, description="Industry: tech, healthcare, finance, education, government, retail"),
    company: Optional[str] = Query(None, description="Company name (partial match)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    rows = database.query_jobs(
        state=state or "",
        industry=industry or "",
        company=company or "",
        limit=limit,
        offset=offset,
    )
    return {"count": len(rows), "offset": offset, "results": rows}


# ---------------------------------------------------------------------------
# GET /stats
# ---------------------------------------------------------------------------

@app.get("/stats", summary="Database statistics")
def get_stats():
    import sqlite3
    from database import get_connection
    conn = get_connection()

    total = database.count_jobs()

    by_source = {
        row["source"]: row["n"]
        for row in conn.execute(
            "SELECT source, COUNT(*) AS n FROM jobs GROUP BY source"
        ).fetchall()
    }
    by_industry = {
        (row["industry"] or "other"): row["n"]
        for row in conn.execute(
            "SELECT industry, COUNT(*) AS n FROM jobs GROUP BY industry"
        ).fetchall()
    }
    top_states = {
        row["state"]: row["n"]
        for row in conn.execute(
            "SELECT state, COUNT(*) AS n FROM jobs WHERE state != '' GROUP BY state ORDER BY n DESC LIMIT 10"
        ).fetchall()
    }
    conn.close()

    return {
        "total_jobs": total,
        "by_source": by_source,
        "by_industry": by_industry,
        "top_states": top_states,
    }


# ---------------------------------------------------------------------------
# POST /scrape
# ---------------------------------------------------------------------------

def _run_scrape(layer1_only: bool, layer2_only: bool, query: str, location: str) -> None:
    global _scrape_running
    _scrape_running = True
    try:
        all_jobs: list[Job] = []
        layer1_keys: set[str] = set()

        if not layer2_only:
            l1_jobs = layer1.scrape_all()
            all_jobs.extend(l1_jobs)
            layer1_keys = {j.dedup_key() for j in l1_jobs}
            logger.info("Layer 1 done: %d jobs", len(l1_jobs))

        if not layer1_only:
            l2_jobs = layer2.scrape_jobspy(
                query=query,
                location=location,
                results_wanted=50,
                existing_keys=layer1_keys,
            )
            all_jobs.extend(l2_jobs)
            logger.info("Layer 2 done: %d new jobs", len(l2_jobs))

        if all_jobs:
            inserted, skipped = database.upsert_jobs(all_jobs)
            logger.info("DB: %d inserted, %d skipped", inserted, skipped)
    finally:
        _scrape_running = False


@app.post("/scrape", summary="Trigger a background scrape")
def trigger_scrape(
    background_tasks: BackgroundTasks,
    layer1_only: bool = Query(False),
    layer2_only: bool = Query(False),
    query: str = Query("engineer", description="Search query for JobSpy (Layer 2)"),
    location: str = Query("United States", description="Location for JobSpy (Layer 2)"),
):
    global _scrape_running
    if _scrape_running:
        raise HTTPException(status_code=409, detail="A scrape is already running.")
    background_tasks.add_task(_run_scrape, layer1_only, layer2_only, query, location)
    return {"status": "scrape started", "layer1_only": layer1_only, "layer2_only": layer2_only}


@app.get("/scrape/status", summary="Check if a scrape is running")
def scrape_status():
    return {"running": _scrape_running}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "total_jobs": database.count_jobs()}
