"""
Filtering logic for state and industry classification.
"""

import re
from models import Job

# ---------------------------------------------------------------------------
# State parsing
# ---------------------------------------------------------------------------

US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}

_STATE_NAME_TO_CODE: dict[str, str] = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC", "washington dc": "DC", "washington d.c.": "DC",
    "washington, dc": "DC", "washington, d.c.": "DC",
}

# Pre-compiled: match ", XX" or " XX " or "(XX)" patterns for 2-letter codes
_STATE_CODE_RE = re.compile(
    r"(?:^|[\s,(/])(" + "|".join(US_STATE_CODES) + r")(?:[\s,/)]|$)"
)


def parse_state(location: str) -> str:
    """
    Extract a US state code from a location string.
    Returns the two-letter code (e.g. 'CA') or '' if not found.
    """
    if not location:
        return ""
    loc = location.strip()

    # Special cases for remote
    if re.search(r"\bremote\b", loc, re.IGNORECASE):
        # Still try to find a state qualifier like "Remote - CA"
        pass

    # Check full state names first (longer match wins)
    loc_lower = loc.lower()
    for name, code in sorted(_STATE_NAME_TO_CODE.items(), key=lambda x: -len(x[0])):
        if name in loc_lower:
            return code

    # Check 2-letter codes
    m = _STATE_CODE_RE.search(loc)
    if m:
        return m.group(1)

    return ""


def filter_by_state(jobs: list[Job], state_code: str) -> list[Job]:
    code = state_code.upper()
    return [j for j in jobs if j.state == code]


# ---------------------------------------------------------------------------
# Industry classification
# ---------------------------------------------------------------------------

INDUSTRY_KEYWORDS: dict[str, list[str]] = {
    "tech": [
        "software", "engineer", "developer", "devops", "cloud", "data",
        "machine learning", "ml", "ai", "artificial intelligence", "platform",
        "backend", "frontend", "fullstack", "full-stack", "infrastructure",
        "security", "sre", "product manager", "ux", "ui", "mobile",
        "android", "ios", "cyber", "network", "database", "analytics",
        "saas", "api", "architecture", "blockchain", "web",
    ],
    "healthcare": [
        "nurse", "physician", "doctor", "medical", "clinical", "health",
        "patient", "hospital", "pharmacist", "pharmacy", "therapist",
        "therapy", "dental", "optometry", "biotech", "bioinformatics",
        "life science", "healthcare", "ehr", "radiology", "surgery",
        "mental health", "behavioral", "caregiver", "wellness",
    ],
    "finance": [
        "finance", "financial", "accounting", "accountant", "analyst",
        "investment", "banking", "bank", "credit", "risk", "compliance",
        "audit", "tax", "insurance", "actuary", "portfolio", "trading",
        "fintech", "payments", "treasury", "underwriter", "loan",
    ],
    "education": [
        "teacher", "teaching", "educator", "curriculum", "instruction",
        "school", "university", "college", "academic", "learning",
        "student", "tutor", "professor", "faculty", "edtech", "training",
        "coach", "coaching", "program manager", "admissions",
    ],
    "government": [
        "government", "federal", "state agency", "public sector",
        "municipality", "city of", "county", "department of", "bureau",
        "regulatory", "policy", "public health", "military", "defense",
        "civil servant", "administrator",
    ],
    "retail": [
        "retail", "store", "shop", "merchandise", "buyer", "visual",
        "e-commerce", "ecommerce", "supply chain", "logistics", "warehouse",
        "fulfillment", "inventory", "purchasing", "vendor", "brand",
        "marketing", "fashion", "apparel", "consumer goods",
    ],
}


def classify_industry(job: Job) -> str:
    """
    Return an industry label based on title + description keywords.
    If a company-level industry is already set, use it as a tiebreaker.
    Returns the best-matching industry key or 'other'.
    """
    text = (job.title + " " + job.description + " " + job.department).lower()

    scores: dict[str, int] = {}
    for ind, keywords in INDUSTRY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score:
            scores[ind] = score

    if not scores:
        return job.industry or "other"

    best = max(scores, key=lambda k: scores[k])
    # If tied and the company-level industry is a candidate, prefer it
    if job.industry and job.industry in scores:
        top_score = scores[best]
        if scores[job.industry] == top_score:
            return job.industry
    return best


def filter_by_industry(jobs: list[Job], category: str) -> list[Job]:
    cat = category.lower()
    return [j for j in jobs if j.industry == cat]


def enrich_jobs(jobs: list[Job]) -> list[Job]:
    """
    In-place enrichment: parse state + classify industry for each job.
    Returns the same list for convenience.
    """
    for job in jobs:
        if not job.state:
            job.state = parse_state(job.location)
        job.industry = classify_industry(job)
    return jobs
