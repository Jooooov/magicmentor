from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional

from ...parsers.cv_parser import parse_cv
from ...memory.persistent_memory import get_user_memory

router = APIRouter()


class CVTextInput(BaseModel):
    cv_text: str
    user_id: Optional[int] = 1
    name: Optional[str] = None
    email: Optional[str] = None


@router.post("/parse-text")
async def parse_cv_from_text(input_data: CVTextInput):
    """Parse CV from pasted text."""
    result = parse_cv(input_data.cv_text, input_type="text")
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # Save to memory
    mem = get_user_memory(input_data.user_id or 1)
    mem.update_profile({
        "name": result.get("name") or input_data.name,
        "email": result.get("email") or input_data.email,
        "current_role": result.get("current_title"),
        "years_experience": result.get("years_experience", 0),
        "location": result.get("location"),
    })
    if result.get("skills"):
        mem.update_skills(current=result["skills"])

    return result


@router.post("/parse-pdf")
async def parse_cv_from_pdf(user_id: int = 1, file: UploadFile = File(...)):
    """Parse CV from uploaded PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    contents = await file.read()
    result = parse_cv(contents, input_type="pdf_bytes")

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # Save to memory
    mem = get_user_memory(user_id)
    mem.update_profile({
        "name": result.get("name"),
        "email": result.get("email"),
        "current_role": result.get("current_title"),
        "years_experience": result.get("years_experience", 0),
        "location": result.get("location"),
    })
    if result.get("skills"):
        mem.update_skills(current=result["skills"])

    return result


@router.get("/memory/{user_id}")
async def get_user_memory_snapshot(user_id: int):
    """Get the persistent memory snapshot for a user."""
    mem = get_user_memory(user_id)
    return mem.data


@router.get("/context/{user_id}")
async def get_context_prompt(user_id: int):
    """Get the formatted context string Claude sees."""
    mem = get_user_memory(user_id)
    return {"context": mem.build_context_prompt()}
