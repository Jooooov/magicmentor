from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

from ...agents.learning_agent import (
    start_learning_session,
    continue_learning,
    run_final_validation,
)
from ...memory.persistent_memory import get_user_memory

router = APIRouter()


class StartRequest(BaseModel):
    skill_name: str
    user_level: str = "beginner"
    user_id: Optional[int] = 1
    context: Optional[str] = None


class ContinueRequest(BaseModel):
    user_response: str
    conversation_history: List[dict]
    skill_name: str
    user_id: Optional[int] = 1


class ValidateRequest(BaseModel):
    skill_name: str
    conversation_history: List[dict]
    user_id: Optional[int] = 1


@router.post("/start")
async def start_session(request: StartRequest):
    """Start a new Socratic learning session for a skill."""
    mem = get_user_memory(request.user_id or 1)
    return start_learning_session(
        skill_name=request.skill_name,
        user_level=request.user_level,
        user_memory=mem,
        context=request.context or "",
    )


@router.post("/continue")
async def continue_session(request: ContinueRequest):
    """Continue an active learning session."""
    mem = get_user_memory(request.user_id or 1)
    return continue_learning(
        user_response=request.user_response,
        conversation_history=request.conversation_history,
        skill_name=request.skill_name,
        user_memory=mem,
    )


@router.post("/validate")
async def validate_skill(request: ValidateRequest):
    """Run a final validation quiz for a skill."""
    mem = get_user_memory(request.user_id or 1)
    return run_final_validation(
        skill_name=request.skill_name,
        conversation_history=request.conversation_history,
        user_memory=mem,
    )
