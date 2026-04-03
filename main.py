#!/usr/bin/env python3
"""
Job Sourcing Platform CLI

Usage:
    python main.py scrape [--layer1-only] [--layer2-only] [--query QUERY]
    python main.py query  [--state CA] [--industry tech] [--company NAME] [--limit 50]
    python main.py stats
    python main.py clear

Examples:
    python main.py scrape
    python main.py scrape --layer1-only
    python main.py query --state CA --industry tech
    python main.py query --state NY --industry healthcare --limit 100
    python main.py stats
"""

import argparse
import json
import logging
import sys

import database
import layer1
import layer2
from filters import filter_by_state, filter_by_industry
from models import Job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


def cmd_scrape(args: argparse.Namespace) -> None:
    database.init_db()

    all_jobs: list[Job] = []
    layer1_keys: set[str] = set()

    if not args.layer2_only:
        print("=== Layer 1: ATS Direct Scraping ===")
        l1_jobs = layer1.scrape_all()
        all_jobs.extend(l1_jobs)
        layer1_keys = {j.dedup_key() for j in l1_jobs}
        print(f"Layer 1 complete: {len(l1_jobs)} unique jobs")

    if not args.layer1_only:
        query = getattr(args, "query", None) or "engineer"
        location = getattr(args, "location", None) or "United States"
        print(f"\n=== Layer 2: JobSpy (query='{query}', location='{location}') ===")
        l2_jobs = layer2.scrape_jobspy(
            query=query,
            location=location,
            results_wanted=50,
            existing_keys=layer1_keys,
        )
        all_jobs.extend(l2_jobs)
        print(f"Layer 2 complete: {len(l2_jobs)} new jobs after dedup")

    if all_jobs:
        inserted, skipped = database.upsert_jobs(all_jobs)
        print(f"\nDatabase: {inserted} inserted, {skipped} skipped (duplicates)")
    else:
        print("No jobs to save.")

    print(f"Total jobs in DB: {database.count_jobs()}")


def cmd_query(args: argparse.Namespace) -> None:
    database.init_db()

    state = (args.state or "").upper()
    industry = (args.industry or "").lower()
    company = args.company or ""
    limit = args.limit

    rows = database.query_jobs(
        state=state,
        industry=industry,
        company=company,
        limit=limit,
    )

    if not rows:
        print("No jobs found matching the given filters.")
        return

    # Pretty print
    print(f"\nFound {len(rows)} job(s):\n")
    for i, row in enumerate(rows, 1):
        print(f"[{i}] {row['title']}")
        print(f"     Company  : {row['company']}")
        print(f"     Location : {row['location']}  (state: {row['state'] or 'n/a'})")
        print(f"     Industry : {row['industry']}")
        print(f"     Source   : {row['source']}")
        print(f"     URL      : {row['url']}")
        print()


def cmd_stats(args: argparse.Namespace) -> None:
    database.init_db()
    total = database.count_jobs()
    print(f"Total jobs in DB: {total}")

    import sqlite3
    from database import get_connection
    conn = get_connection()

    print("\nBy source:")
    for row in conn.execute("SELECT source, COUNT(*) AS n FROM jobs GROUP BY source ORDER BY n DESC").fetchall():
        print(f"  {row['source']:<15} {row['n']}")

    print("\nBy industry:")
    for row in conn.execute("SELECT industry, COUNT(*) AS n FROM jobs GROUP BY industry ORDER BY n DESC").fetchall():
        print(f"  {row['industry'] or 'other':<15} {row['n']}")

    print("\nTop states:")
    for row in conn.execute(
        "SELECT state, COUNT(*) AS n FROM jobs WHERE state != '' GROUP BY state ORDER BY n DESC LIMIT 10"
    ).fetchall():
        print(f"  {row['state']:<6} {row['n']}")

    conn.close()


def cmd_clear(args: argparse.Namespace) -> None:
    n = database.delete_all_jobs()
    print(f"Deleted {n} job(s) from the database.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Job Sourcing Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # scrape
    p_scrape = sub.add_parser("scrape", help="Scrape jobs from ATS + aggregators")
    p_scrape.add_argument("--layer1-only", action="store_true", help="Only run Layer 1 (ATS direct)")
    p_scrape.add_argument("--layer2-only", action="store_true", help="Only run Layer 2 (JobSpy)")
    p_scrape.add_argument("--query", default="engineer", help="Search query for JobSpy (Layer 2)")
    p_scrape.add_argument("--location", default="United States", help="Location for JobSpy (Layer 2)")

    # query
    p_query = sub.add_parser("query", help="Query stored jobs")
    p_query.add_argument("--state", help="Filter by US state code (e.g. CA, NY)")
    p_query.add_argument("--industry", help="Filter by industry (tech, healthcare, finance, etc.)")
    p_query.add_argument("--company", help="Filter by company name (partial match)")
    p_query.add_argument("--limit", type=int, default=50, help="Max results to display")

    # stats
    sub.add_parser("stats", help="Show database statistics")

    # clear
    sub.add_parser("clear", help="Delete all jobs from the database")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "scrape": cmd_scrape,
        "query": cmd_query,
        "stats": cmd_stats,
        "clear": cmd_clear,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
