"""
Mentor Agent  (Perplexity sonar-pro)
=====================================
sonar-pro has built-in real-time web search — perfect for career mentoring:
  • Automatically knows current job market trends
  • Can verify current salary ranges live
  • Knows which technologies are trending RIGHT NOW

Cost: $3/$15 per 1M tokens (vs Opus $5/$25 = 40% cheaper on input, 40% cheaper on output)
"""

import json

from ..ai_client import chat, chat_single, SONAR_PRO
from ..memory.persistent_memory import UserMemory

MENTOR_SYSTEM = """You are MagicMentor — an elite AI career mentor with real-time web search.

Your approach:
- Deeply analyse the candidate's profile, strengths, and gaps
- Use your web search to get CURRENT job market data (don't rely on old knowledge)
- Give specific, actionable, honest advice — never generic platitudes
- Connect every recommendation to concrete job opportunities available right now
- Be encouraging but realistic about timelines and difficulty
- Adapt based on what you know about this person from their memory/history

When analysing skill gaps, search for:
- Current job postings for the target role
- Which skills appear most in those postings
- Current average salaries in the candidate's location
- For each skill gap, find 2-3 specific courses/resources with real URLs valid as of today.
  Include free options (official docs, YouTube, free tiers) AND paid courses when relevant.

You have persistent memory about this user. Use it for personalised, continuity-aware advice."""


def analyze_profile(
    cv_text: str,
    market_insights: dict = None,
    user_memory: UserMemory = None,
) -> dict:
    """Full career analysis: skill gaps, learning roadmap, recommended roles."""

    memory_context = user_memory.build_context_prompt() if user_memory else ""
    market_context = ""
    if market_insights and "top_required_skills" in market_insights:
        market_context = f"\nCurrent Job Market Data:\n{json.dumps(market_insights, indent=2)}"

    system = MENTOR_SYSTEM
    if memory_context:
        system += f"\n\n{memory_context}"

    prompt = f"""Analyse this CV and provide a comprehensive career development plan.
Use your web search to validate skill demand and salary ranges.

CV/Profile:
{cv_text}
{market_context}

Return ONLY a JSON object (no other text):
{{
    "career_summary": "Brief narrative of this person's profile and trajectory",
    "current_skills": [
        {{"name": "Python", "level": "intermediate", "years": 2, "category": "programming"}}
    ],
    "key_strengths": ["strength 1", "strength 2"],
    "skill_gaps": [
        {{
            "skill": "FastAPI",
            "priority": 1,
            "category": "framework",
            "reason": "Why this skill matters for their target role",
            "builds_on": "Django experience they already have",
            "estimated_learning_time": "1-2 weeks",
            "job_market_demand": "high",
            "resources": [
                {{"name": "FastAPI official tutorial", "url": "https://fastapi.tiangolo.com/tutorial/", "free": true, "type": "docs"}},
                {{"name": "TestDriven.io FastAPI course", "url": "https://testdriven.io/courses/tdd-fastapi/", "free": false, "type": "course"}}
            ]
        }}
    ],
    "recommended_roles": [
        {{
            "title": "Backend Developer",
            "match_percentage": 65,
            "required_upskilling": ["FastAPI", "Docker"],
            "realistic_timeline": "3 months",
            "avg_salary": "40-55k EUR"
        }}
    ],
    "learning_roadmap": [
        {{
            "week": 1,
            "focus": "FastAPI fundamentals",
            "daily_hours": 2,
            "milestones": ["Build first REST API", "Understand async"],
            "why_now": "Foundation for all backend work"
        }}
    ],
    "next_action": "The single most important thing to do TODAY"
}}"""

    response_text = chat(
        messages=[{"role": "user", "content": prompt}],
        model=SONAR_PRO,
        system=system,
        max_tokens=6000,
        temperature=0.2,
    )

    result = _extract_json(response_text)

    # Save to persistent memory
    if user_memory and result and "skill_gaps" in result:
        top_gaps = [g["skill"] for g in result.get("skill_gaps", [])[:3]]
        user_memory.add_mentor_note(
            f"CV analysed. Top gaps: {', '.join(top_gaps)}. {result.get('career_summary', '')[:100]}"
        )
        if result.get("current_skills"):
            user_memory.update_skills(
                current=result["current_skills"],
                targets=[{"name": g["skill"], "priority": g["priority"]} for g in result.get("skill_gaps", [])],
            )
        # Save courses from skill gap resources
        user_memory.save_courses_from_gaps(result.get("skill_gaps", []))
        # Save full analysis so learning session can use it across sessions
        user_memory.save_mentor_analysis(
            skill_gaps=result.get("skill_gaps", []),
            learning_roadmap=result.get("learning_roadmap", []),
            recommended_roles=result.get("recommended_roles", []),
        )
        user_memory.add_session_summary(
            session_type="mentor_analysis",
            summary=f"CV analysed. {len(result.get('skill_gaps', []))} skill gaps identified.",
            key_insights=[result.get("next_action", "")],
        )

    return result


def chat_with_mentor(
    user_message: str,
    conversation_history: list,
    user_memory: UserMemory = None,
    profile_context: str = "",
) -> dict:
    """Conversational mentor chat with persistent memory and web search."""
    memory_context = user_memory.build_context_prompt() if user_memory else ""

    system = MENTOR_SYSTEM
    if memory_context:
        system += f"\n\n{memory_context}"
    if profile_context:
        system += f"\n\nProfile snapshot:\n{profile_context[:500]}"

    messages = conversation_history.copy()
    messages.append({"role": "user", "content": user_message})

    response_text = chat(
        messages=messages,
        model=SONAR_PRO,
        system=system,
        max_tokens=2048,
        temperature=0.3,
    )

    # Save note if user revealed something important
    mentor_note = None
    if user_memory and any(kw in user_message.lower() for kw in ["goal", "want", "dream", "struggle", "hate", "love", "worried"]):
        mentor_note = f"User said: {user_message[:100]}"
        user_memory.add_mentor_note(mentor_note)

    return {
        "response": response_text,
        "history": messages + [{"role": "assistant", "content": response_text}],
        "mentor_note": mentor_note,
    }


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    return {"raw_analysis": text}
