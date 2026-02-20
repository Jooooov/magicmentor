"""
Job Matching Agent  (Perplexity sonar-pro)
==========================================
sonar-pro has web search — it can look up the company and verify the tech stack live.
This gives more accurate match scores than a model working from stale knowledge.

Cost: $3/$15 per 1M tokens (vs Opus $5/$25)
"""

import json
from typing import List, Dict

from ..ai_client import chat, SONAR_PRO

MATCHER_SYSTEM = """You are MagicMentor's Job Match Analyst with real-time web search.

When scoring a job match, you can search for:
- Current skill requirements for this type of role
- Company information and tech stack
- Whether mentioned technologies are still relevant/current

Scoring methodology:
- current_match_score (0-100): What the candidate already meets
  80+  : Strong match, apply immediately
  60-79: Good match, worth applying with minor prep
  40-59: Apply after 2-4 weeks upskilling
  <40  : Significant gap, 1-3 months needed

- potential_match_score: Score after completing recommended learning path

Be precise and honest. Consider skill levels (advanced > intermediate > beginner)."""


def score_single_job(user_profile: dict, job: dict) -> dict:
    """Score a single job against the user's profile."""
    prompt = f"""Score this job match.

CANDIDATE:
{json.dumps(user_profile, indent=2)[:2000]}

JOB: {job.get('title', '')} at {job.get('company', '')}
DESCRIPTION:
{job.get('description', '')[:3000]}

Return ONLY this JSON (no other text):
{{
    "current_match_score": 72,
    "potential_match_score": 88,
    "matching_skills": ["Python", "Django"],
    "missing_skills": [
        {{"skill": "Docker", "importance": "critical", "learn_time": "1 week"}},
        {{"skill": "Kubernetes", "importance": "nice_to_have", "learn_time": "3 weeks"}}
    ],
    "quick_wins": ["Docker basics — 1 week, boosts match by 15%"],
    "recommendation": "Apply after upskilling",
    "reasoning": "Strong Python/Django match but missing containerisation skills"
}}"""

    response_text = chat(
        messages=[{"role": "user", "content": prompt}],
        model=SONAR_PRO,
        system=MATCHER_SYSTEM,
        max_tokens=1024,
        temperature=0.1,
    )

    start = response_text.find("{")
    end = response_text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(response_text[start:end])
        except json.JSONDecodeError:
            pass

    return {
        "current_match_score": 0,
        "potential_match_score": 0,
        "matching_skills": [],
        "missing_skills": [],
        "quick_wins": [],
        "recommendation": "Could not analyse",
        "reasoning": response_text[:200],
    }


def rank_jobs(user_profile: dict, jobs: List[Dict], max_jobs: int = 15) -> List[Dict]:
    """Score and rank jobs by match. Returns sorted by current_match_score desc."""
    ranked = []
    jobs_to_score = jobs[:max_jobs]

    print(f"[matcher] Scoring {len(jobs_to_score)} jobs with Perplexity sonar-pro...")
    for i, job in enumerate(jobs_to_score):
        print(f"[matcher] {i+1}/{len(jobs_to_score)}: {job.get('title', '')}...")
        score_data = score_single_job(user_profile, job)
        ranked.append({
            **job,
            "match_score": score_data.get("current_match_score", 0),
            "potential_match_score": score_data.get("potential_match_score", 0),
            "matching_skills": score_data.get("matching_skills", []),
            "missing_skills": score_data.get("missing_skills", []),
            "quick_wins": score_data.get("quick_wins", []),
            "recommendation": score_data.get("recommendation", ""),
            "reasoning": score_data.get("reasoning", ""),
        })

    return sorted(ranked, key=lambda x: x.get("match_score", 0), reverse=True)
