"""Pipeline agents for Domain Hunter REVENANT.

Exports the run() entry point for each pipeline stage:
  - scout.run: Stage 1 — Discovery (raw feeds -> DomainCandidate)
  - sentinel.run: Stage 2 — SEO Vetting (DomainCandidate -> VettedDomain)
  - archivist.run: Stage 3 — History Verification (VettedDomain -> VerifiedDomain)
  - spectre.run: Stage 4 — Niche Relevance Scoring (VerifiedDomain -> ScoredDomain)
  - oracle.run: Stage 5 — Final Verdict (ScoredDomain -> DomainVerdict)
"""
from __future__ import annotations

from agents.archivist import run as archivist_run
from agents.oracle import run as oracle_run
from agents.scout import run as scout_run
from agents.sentinel import run as sentinel_run
from agents.spectre import run as spectre_run

__all__: list[str] = [
    "scout_run",
    "sentinel_run",
    "archivist_run",
    "spectre_run",
    "oracle_run",
]
