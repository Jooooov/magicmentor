"""
Job Scraper
===========
Scrapes job postings from multiple free sources using python-jobspy:
  - LinkedIn
  - Indeed
  - Glassdoor
  - ZipRecruiter
  - Google Jobs

Also integrates Perplexity API for AI-powered job market research.
"""

from typing import List, Dict, Optional

from ..config import settings


# ── JobSpy scraper ──────────────────────────────────────────────────────────

def scrape_jobs(
    search_term: str,
    location: str = None,
    site_names: List[str] = None,
    results_wanted: int = None,
    hours_old: int = None,
    is_remote: bool = False,
) -> List[Dict]:
    """
    Scrape job postings from multiple free job boards.

    Returns a list of job dicts with normalized fields.
    Falls back to Perplexity search if jobspy fails.

    Note: Glassdoor only works for US locations — excluded by default for Portugal.
    """
    location = location or settings.DEFAULT_LOCATION
    results_wanted = results_wanted or settings.JOBS_MAX_RESULTS
    hours_old = hours_old or settings.JOBS_MAX_HOURS_OLD

    # Glassdoor geo-restricted to US — use LinkedIn + Indeed + ZipRecruiter for Portugal/EU
    if site_names is None:
        is_us = any(term in location.lower() for term in ["united states", "usa", "us", "new york", "california"])
        site_names = ["linkedin", "indeed", "zip_recruiter", "google"] if is_us else ["linkedin", "indeed", "google"]

    try:
        from jobspy import scrape_jobs as jobspy_scrape

        jobs_df = jobspy_scrape(
            site_name=site_names,
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            hours_old=hours_old,
            is_remote=is_remote,
            country_indeed="portugal" if "portugal" in location.lower() else "worldwide",
            verbose=False,
        )

        if jobs_df is None or jobs_df.empty:
            print("[scraper] JobSpy returned no results, falling back to Perplexity")
            return search_jobs_perplexity(search_term, location)

        jobs = []
        for _, row in jobs_df.iterrows():
            description = str(row.get("description", "") or "")
            jobs.append({
                "title": str(row.get("title", "") or ""),
                "company": str(row.get("company", "") or ""),
                "location": str(row.get("location", "") or ""),
                "description": description[:5000],
                "url": str(row.get("job_url", "") or ""),
                "source": str(row.get("site", "") or ""),
                "salary_min": _safe_float(row.get("min_amount")),
                "salary_max": _safe_float(row.get("max_amount")),
                "date_posted": str(row.get("date_posted", "") or ""),
                "is_remote": bool(row.get("is_remote", False)),
            })

        print(f"[scraper] JobSpy found {len(jobs)} jobs for '{search_term}'")
        return jobs

    except ImportError:
        print("[scraper] python-jobspy not installed, using Perplexity fallback")
        return search_jobs_perplexity(search_term, location)
    except Exception as e:
        print(f"[scraper] JobSpy error: {e}, using Perplexity fallback")
        return search_jobs_perplexity(search_term, location)


def _safe_float(val) -> Optional[float]:
    try:
        return float(val) if val is not None else None
    except (ValueError, TypeError):
        return None


# ── Perplexity job research ─────────────────────────────────────────────────

def search_jobs_perplexity(search_term: str, location: str = "Portugal") -> List[Dict]:
    """
    Use Perplexity's real-time web search to find job postings.
    Returns structured job data extracted from web results.
    """
    if not settings.PERPLEXITY_API_KEY:
        print("[perplexity] No API key configured")
        return _mock_jobs(search_term, location)

    try:
        from openai import OpenAI

        pplx = OpenAI(
            api_key=settings.PERPLEXITY_API_KEY,
            base_url="https://api.perplexity.ai",
        )

        prompt = f"""Search for current job postings for "{search_term}" in {location}.

For each job found, extract:
- Job title
- Company name
- Location (city/remote)
- Key required skills (list)
- Salary range if mentioned
- Job URL or apply link
- Whether remote is possible

Return the top 10 jobs as a JSON array:
[
  {{
    "title": "job title",
    "company": "company",
    "location": "city or Remote",
    "required_skills": ["skill1", "skill2"],
    "salary_range": "35k-50k EUR" or null,
    "url": "https://...",
    "is_remote": true/false,
    "description_summary": "2-3 sentence summary"
  }}
]

Only return the JSON array, no other text."""

        response = pplx.chat.completions.create(
            model=settings.PERPLEXITY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000,
        )

        content = response.choices[0].message.content
        start = content.find("[")
        end = content.rfind("]") + 1
        if start >= 0 and end > start:
            import json
            raw_jobs = json.loads(content[start:end])
            # Normalize to our schema
            jobs = []
            for j in raw_jobs:
                jobs.append({
                    "title": j.get("title", ""),
                    "company": j.get("company", ""),
                    "location": j.get("location", ""),
                    "description": j.get("description_summary", ""),
                    "url": j.get("url", ""),
                    "source": "perplexity",
                    "salary_min": None,
                    "salary_max": None,
                    "date_posted": "recent",
                    "is_remote": j.get("is_remote", False),
                    "required_skills": j.get("required_skills", []),
                })
            print(f"[perplexity] Found {len(jobs)} jobs for '{search_term}'")
            return jobs

    except Exception as e:
        print(f"[perplexity] Error: {e}")

    return _mock_jobs(search_term, location)


def get_market_insights(role: str, skills: List[str] = None) -> dict:
    """
    Use Perplexity to research current job market trends for a role.
    Returns insights about demand, salary, and in-demand skills.
    """
    if not settings.PERPLEXITY_API_KEY:
        return {"error": "Perplexity API key not configured"}

    try:
        from openai import OpenAI
        import json

        pplx = OpenAI(
            api_key=settings.PERPLEXITY_API_KEY,
            base_url="https://api.perplexity.ai",
        )

        skills_context = f"The candidate currently has: {', '.join(skills)}" if skills else ""

        prompt = f"""Research the current job market for "{role}" roles in 2025-2026.
{skills_context}

Provide a JSON analysis:
{{
    "market_demand": "high|medium|low",
    "avg_salary_range": "X-Y EUR/year",
    "top_required_skills": [
        {{"skill": "name", "frequency": "very common|common|occasional", "trend": "rising|stable|declining"}}
    ],
    "emerging_skills": ["skill1", "skill2"],
    "common_job_titles": ["title1", "title2"],
    "market_summary": "2-3 sentence overview of the market",
    "advice": "Specific advice for someone targeting this role"
}}

Return only the JSON."""

        response = pplx.chat.completions.create(
            model=settings.PERPLEXITY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
        )

        content = response.choices[0].message.content
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])

    except Exception as e:
        print(f"[perplexity] Market insights error: {e}")

    return {"error": "Could not fetch market insights"}


# ── Mock fallback ───────────────────────────────────────────────────────────

def _mock_jobs(search_term: str, location: str) -> List[Dict]:
    """Fallback mock jobs for local testing."""
    return [
        {
            "title": f"Senior {search_term}",
            "company": "Tech Corp Portugal",
            "location": location,
            "description": f"We need a {search_term} with Python, FastAPI, PostgreSQL, Docker, AWS, React, TypeScript, CI/CD. 3+ years experience.",
            "url": "https://example.com/job/1",
            "source": "mock",
            "salary_min": 50000,
            "salary_max": 75000,
            "date_posted": "2025-01-15",
            "is_remote": True,
        },
        {
            "title": f"Mid-level {search_term}",
            "company": "StartupXYZ",
            "location": location,
            "description": f"{search_term} position. Skills: Python, Django, React, PostgreSQL, Git. 1-3 years experience.",
            "url": "https://example.com/job/2",
            "source": "mock",
            "salary_min": 35000,
            "salary_max": 50000,
            "date_posted": "2025-01-14",
            "is_remote": False,
        },
        {
            "title": f"Junior {search_term}",
            "company": "Digital Agency",
            "location": location,
            "description": f"Entry-level {search_term}. HTML, CSS, JavaScript, Python basics. Fresh graduates welcome.",
            "url": "https://example.com/job/3",
            "source": "mock",
            "salary_min": 22000,
            "salary_max": 32000,
            "date_posted": "2025-01-13",
            "is_remote": False,
        },
    ]
