"""
Quick smoke tests for each scraper and the filter/dedup logic.
Run with: python test_scrapers.py
"""

import sys
import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s — %(message)s")

from models import Job
from filters import parse_state, classify_industry, enrich_jobs
import database
from pathlib import Path

TEMP_DB = Path("/tmp/test_jobs.db")


def test_state_parser():
    cases = [
        ("San Francisco, CA", "CA"),
        ("New York, NY", "NY"),
        ("Austin, Texas", "TX"),
        ("Remote", ""),
        ("Remote - Seattle, WA", "WA"),
        ("Chicago, Illinois", "IL"),
        ("", ""),
        ("Washington, DC", "DC"),
        ("Washington, D.C.", "DC"),
    ]
    ok = True
    for loc, expected in cases:
        got = parse_state(loc)
        status = "OK" if got == expected else "FAIL"
        if status == "FAIL":
            ok = False
        print(f"  [{status}] parse_state({loc!r}) => {got!r} (expected {expected!r})")
    return ok


def test_industry_classifier():
    jobs = [
        Job("test", "Acme", "Senior Software Engineer", "CA", "http://x", industry="tech"),
        Job("test", "Acme", "Registered Nurse", "NY", "http://x", industry="healthcare"),
        Job("test", "Acme", "Financial Analyst", "TX", "http://x", industry="finance"),
        Job("test", "Acme", "High School Teacher", "FL", "http://x", industry="education"),
    ]
    expected = ["tech", "healthcare", "finance", "education"]
    ok = True
    for job, exp in zip(jobs, expected):
        got = classify_industry(job)
        status = "OK" if got == exp else "FAIL"
        if status == "FAIL":
            ok = False
        print(f"  [{status}] classify_industry({job.title!r}) => {got!r} (expected {exp!r})")
    return ok


def test_dedup():
    j1 = Job("greenhouse", "Acme", "Engineer", "San Francisco, CA", "http://a")
    j2 = Job("lever", "Acme", "Engineer", "San Francisco, CA", "http://b")  # same logical job
    j3 = Job("greenhouse", "Acme", "Designer", "San Francisco, CA", "http://c")
    assert j1.dedup_key() == j2.dedup_key(), "same company+title+location should dedup"
    assert j1.dedup_key() != j3.dedup_key(), "different title should not dedup"
    print("  [OK] Dedup key logic")
    return True


def test_database():
    if TEMP_DB.exists():
        TEMP_DB.unlink()
    database.init_db(TEMP_DB)

    jobs = [
        Job("greenhouse", "Stripe", "Engineer", "San Francisco, CA", "http://1", state="CA", industry="tech"),
        Job("lever", "Zapier", "Designer", "New York, NY", "http://2", state="NY", industry="tech"),
        Job("ashby", "Linear", "PM", "Remote", "http://3", state="", industry="tech"),
    ]
    ins, skip = database.upsert_jobs(jobs, TEMP_DB)
    assert ins == 3, f"Expected 3 inserted, got {ins}"
    assert skip == 0, f"Expected 0 skipped, got {skip}"

    # Duplicate insert
    ins2, skip2 = database.upsert_jobs(jobs[:1], TEMP_DB)
    assert ins2 == 0 and skip2 == 1, "Duplicate should be skipped"

    rows = database.query_jobs(state="CA", db_path=TEMP_DB)
    assert len(rows) == 1, f"Expected 1 CA job, got {len(rows)}"

    rows_tech = database.query_jobs(industry="tech", db_path=TEMP_DB)
    assert len(rows_tech) == 3, f"Expected 3 tech jobs, got {len(rows_tech)}"

    print(f"  [OK] DB: 3 inserted, dedup works, state/industry query works")
    TEMP_DB.unlink()
    return True


def test_greenhouse_live():
    """Live test — hits Greenhouse API for Airbnb."""
    from scrapers import greenhouse
    jobs = greenhouse.fetch_jobs("Airbnb", "airbnb")
    if not jobs:
        print("  [WARN] Greenhouse/Airbnb returned 0 jobs (slug may have changed)")
        return True
    print(f"  [OK] Greenhouse/Airbnb: {len(jobs)} jobs, sample: {jobs[0].title!r} @ {jobs[0].location!r}")
    return True


def test_lever_live():
    """Live test — hits Lever API for Zapier."""
    from scrapers import lever
    jobs = lever.fetch_jobs("Zapier", "zapier")
    if not jobs:
        print("  [WARN] Lever/Zapier returned 0 jobs (slug may have changed)")
        return True
    print(f"  [OK] Lever/Zapier: {len(jobs)} jobs, sample: {jobs[0].title!r} @ {jobs[0].location!r}")
    return True


def test_ashby_live():
    """Live test — hits Ashby API for Linear."""
    from scrapers import ashby
    jobs = ashby.fetch_jobs("Linear", "linear")
    if not jobs:
        print("  [WARN] Ashby/Linear returned 0 jobs (slug may have changed)")
        return True
    print(f"  [OK] Ashby/Linear: {len(jobs)} jobs, sample: {jobs[0].title!r} @ {jobs[0].location!r}")
    return True


def main():
    suites = [
        ("State parser", test_state_parser),
        ("Industry classifier", test_industry_classifier),
        ("Dedup keys", test_dedup),
        ("Database", test_database),
        ("Greenhouse API (live)", test_greenhouse_live),
        ("Lever API (live)", test_lever_live),
        ("Ashby API (live)", test_ashby_live),
    ]
    results = []
    for name, fn in suites:
        print(f"\n--- {name} ---")
        try:
            ok = fn()
            results.append((name, ok))
        except Exception as e:
            print(f"  [ERROR] {e}")
            results.append((name, False))

    print("\n=== Summary ===")
    all_ok = True
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_ok = False
        print(f"  {status}  {name}")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
