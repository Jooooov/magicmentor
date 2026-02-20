from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

from ...scrapers.job_scraper import scrape_jobs, get_market_insights
from ...agents.matching_agent import rank_jobs
from ...memory.persistent_memory import get_user_memory

router = APIRouter()


class JobSearchRequest(BaseModel):
    search_term: str
    location: Optional[str] = None
    results_wanted: int = 20
    is_remote: bool = False
    sites: Optional[List[str]] = None
    user_id: Optional[int] = 1
    score_matches: bool = True


class MarketRequest(BaseModel):
    role: str
    user_id: Optional[int] = 1


@router.post("/search")
async def search_jobs(request: JobSearchRequest):
    """Scrape job postings from multiple job boards."""
    jobs = scrape_jobs(
        search_term=request.search_term,
        location=request.location,
        site_names=request.sites,
        results_wanted=request.results_wanted,
        is_remote=request.is_remote,
    )
    return {"jobs": jobs, "total": len(jobs)}


@router.post("/match")
async def match_jobs(request: JobSearchRequest):
    """Scrape jobs and rank by AI match score against user profile."""
    mem = get_user_memory(request.user_id or 1)

    jobs = scrape_jobs(
        search_term=request.search_term,
        location=request.location,
        site_names=request.sites,
        results_wanted=request.results_wanted,
        is_remote=request.is_remote,
    )

    if not jobs:
        return {"jobs": [], "total": 0, "message": "No jobs found"}

    if request.score_matches:
        user_profile = {
            "skills": mem.skills.get("current", []),
            "completed_skills": mem.skills.get("completed", []),
            "target_role": request.search_term,
            **mem.profile,
        }
        ranked = rank_jobs(user_profile, jobs)
    else:
        ranked = jobs

    return {"jobs": ranked, "total": len(ranked)}


@router.post("/market-insights")
async def market_research(request: MarketRequest):
    """Get real-time job market insights for a role via Perplexity."""
    mem = get_user_memory(request.user_id or 1)
    current_skills = [s.get("name") for s in mem.skills.get("current", [])]
    return get_market_insights(request.role, current_skills)
