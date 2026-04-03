"""
SQLite persistence layer for the job sourcing platform.
"""

import sqlite3
import logging
from pathlib import Path
from models import Job

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "jobs.db"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    conn = get_connection(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            dedup_key   TEXT PRIMARY KEY,
            source      TEXT NOT NULL,
            company     TEXT NOT NULL,
            title       TEXT NOT NULL,
            location    TEXT NOT NULL,
            state       TEXT NOT NULL DEFAULT '',
            url         TEXT NOT NULL,
            job_id      TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            industry    TEXT NOT NULL DEFAULT '',
            department  TEXT NOT NULL DEFAULT '',
            inserted_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_state     ON jobs(state)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_industry  ON jobs(industry)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_company   ON jobs(company)")
    conn.commit()
    conn.close()
    logger.debug("Database initialised at %s", db_path)


def upsert_jobs(jobs: list[Job], db_path: Path = DB_PATH) -> tuple[int, int]:
    """Insert new jobs; skip duplicates. Returns (inserted, skipped)."""
    conn = get_connection(db_path)
    inserted = skipped = 0
    for job in jobs:
        key = job.dedup_key()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO jobs
                    (dedup_key, source, company, title, location, state,
                     url, job_id, description, industry, department)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (key, job.source, job.company, job.title, job.location,
                 job.state, job.url, job.job_id, job.description,
                 job.industry, job.department),
            )
            if conn.total_changes > 0:
                inserted += 1
            else:
                skipped += 1
        except sqlite3.Error as e:
            logger.error("DB upsert error for %s/%s: %s", job.company, job.title, e)
            skipped += 1
    conn.commit()
    conn.close()
    return inserted, skipped


def query_jobs(
    state: str = "",
    industry: str = "",
    company: str = "",
    limit: int = 200,
    offset: int = 0,
    db_path: Path = DB_PATH,
) -> list[dict]:
    conn = get_connection(db_path)
    clauses: list[str] = []
    params: list = []
    if state:
        clauses.append("state = ?")
        params.append(state.upper())
    if industry:
        clauses.append("industry = ?")
        params.append(industry.lower())
    if company:
        clauses.append("company LIKE ?")
        params.append(f"%{company}%")

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT source, company, title, location, state, url,
               industry, department, inserted_at
        FROM jobs
        {where}
        ORDER BY inserted_at DESC
        LIMIT ? OFFSET ?
    """
    params += [limit, offset]
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_jobs(db_path: Path = DB_PATH) -> int:
    conn = get_connection(db_path)
    n = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    conn.close()
    return n


def delete_all_jobs(db_path: Path = DB_PATH) -> int:
    conn = get_connection(db_path)
    conn.execute("DELETE FROM jobs")
    conn.commit()
    n = conn.total_changes
    conn.close()
    return n
