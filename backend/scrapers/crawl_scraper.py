"""
Crawl4AI Job Scraper
====================
Uses Crawl4AI — the most capable open-source AI web scraper (2024-2026)
to directly scrape job postings from websites as a fallback.

Crawl4AI features:
- Async/concurrent scraping
- JS rendering via Playwright
- LLM-powered extraction (extracts structured data using Claude/local models)
- Anti-bot bypass capabilities
- 6x faster than Selenium

Use case: When jobspy fails or returns 0 results for a niche search,
crawl4ai can directly scrape specific job boards.
"""

import asyncio
import json
from typing import List, Dict

from ..config import settings


async def scrape_jobs_crawl4ai(
    search_term: str,
    location: str = "Portugal",
    max_results: int = 20,
) -> List[Dict]:
    """
    Use Crawl4AI with Claude to extract job listings from Indeed/LinkedIn.
    LLM-powered extraction ensures clean structured data even from complex pages.
    """
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
        from crawl4ai.extraction_strategy import LLMExtractionStrategy
    except ImportError:
        print("[crawl4ai] Not installed. Run: pip install crawl4ai && crawl4ai-setup")
        return []

    # Target URL (Indeed Portugal)
    search_encoded = search_term.replace(" ", "+")
    url = f"https://pt.indeed.com/jobs?q={search_encoded}&l={location.replace(' ', '+')}"

    # LLM extraction schema
    extraction_schema = {
        "name": "JobListings",
        "baseSelector": "div.job_seen_beacon",
        "fields": [
            {"name": "title", "selector": "h2.jobTitle", "type": "text"},
            {"name": "company", "selector": "span.companyName", "type": "text"},
            {"name": "location", "selector": "div.companyLocation", "type": "text"},
            {"name": "description", "selector": "div.job-snippet", "type": "text"},
            {"name": "url", "selector": "h2.jobTitle a", "type": "attribute", "attribute": "href"},
        ],
    }

    extraction_strategy = LLMExtractionStrategy(
        provider="openai/gpt-4o-mini",   # or swap for any provider supported by crawl4ai
        api_token=settings.PERPLEXITY_API_KEY,
        schema=json.dumps(extraction_schema),
        extraction_type="schema",
        instruction=f"Extract job listings for '{search_term}' in {location}. Return a list of job objects.",
    )

    browser_config = BrowserConfig(headless=True, verbose=False)
    run_config = CrawlerRunConfig(
        extraction_strategy=extraction_strategy,
        cache_mode=CacheMode.BYPASS,
        js_code=["window.scrollTo(0, document.body.scrollHeight);"],
        wait_for="css:div.job_seen_beacon",
    )

    jobs = []
    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config)
            if result.success and result.extracted_content:
                raw = json.loads(result.extracted_content)
                for item in raw[:max_results]:
                    jobs.append({
                        "title": item.get("title", ""),
                        "company": item.get("company", ""),
                        "location": item.get("location", location),
                        "description": item.get("description", ""),
                        "url": item.get("url", ""),
                        "source": "crawl4ai/indeed",
                        "salary_min": None,
                        "salary_max": None,
                        "date_posted": "recent",
                        "is_remote": "remote" in item.get("location", "").lower(),
                    })
                print(f"[crawl4ai] Extracted {len(jobs)} jobs")
    except Exception as e:
        print(f"[crawl4ai] Error: {e}")

    return jobs


def scrape_jobs_sync(search_term: str, location: str = "Portugal", max_results: int = 20) -> List[Dict]:
    """Sync wrapper for crawl4ai scraping."""
    return asyncio.run(scrape_jobs_crawl4ai(search_term, location, max_results))
