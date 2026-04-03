"""
Core data models for the job sourcing platform.
"""

from dataclasses import dataclass, field
import hashlib


@dataclass
class Job:
    source: str          # "greenhouse" | "lever" | "ashby" | "indeed" | "google"
    company: str
    title: str
    location: str
    url: str
    job_id: str = ""
    description: str = ""
    industry: str = ""
    department: str = ""
    state: str = ""      # parsed US state code, e.g. "CA"

    def dedup_key(self) -> str:
        """Stable hash for deduplication: company + title + location."""
        raw = f"{self.company.lower()}|{self.title.lower()}|{self.location.lower()}"
        return hashlib.sha256(raw.encode()).hexdigest()


@dataclass
class Company:
    name: str
    ats: str   # "greenhouse" | "lever" | "ashby"
    slug: str
    industry: str = ""
