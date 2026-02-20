from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

from ...agents.mentor_agent import analyze_profile, chat_with_mentor
from ...scrapers.job_scraper import get_market_insights
from ...memory.persistent_memory import get_user_memory

router = APIRouter()


class AnalyzeRequest(BaseModel):
    cv_text: str
    user_id: Optional[int] = 1
    target_role: Optional[str] = None
    fetch_market_data: bool = True


class ChatRequest(BaseModel):
    message: str
    user_id: Optional[int] = 1
    conversation_history: List[dict] = []
    profile_context: Optional[str] = None


@router.post("/analyze")
async def analyze_career(request: AnalyzeRequest):
    """
    Full career analysis: skill gaps, learning roadmap, recommended roles.
    Optionally fetches real-time market data from Perplexity.
    """
    mem = get_user_memory(request.user_id or 1)
    market_insights = None

    if request.fetch_market_data and request.target_role:
        current_skills = [s.get("name") for s in mem.skills.get("current", [])]
        market_insights = get_market_insights(request.target_role, current_skills)

    result = analyze_profile(
        cv_text=request.cv_text,
        market_insights=market_insights,
        user_memory=mem,
    )

    return {**result, "market_insights": market_insights}


@router.post("/chat")
async def mentor_chat(request: ChatRequest):
    """Conversational mentor chat with persistent memory."""
    mem = get_user_memory(request.user_id or 1)
    return chat_with_mentor(
        user_message=request.message,
        conversation_history=request.conversation_history,
        user_memory=mem,
        profile_context=request.profile_context or "",
    )
