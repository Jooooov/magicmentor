"""
CV Updater Agent
================
Uses the local MLX model to suggest concrete CV updates based on
the user's learning progress: validated skills, completed courses,
and in-progress studies.

Returns a structured dict with ready-to-use CV sections/bullets.
"""

import json
from datetime import datetime

from ..ai_client import chat_single, LOCAL_MODEL
from ..memory.persistent_memory import UserMemory


SYSTEM = """You are an expert CV writer specialising in tech roles.
Your job is to translate learning progress into polished, concrete CV content.

Rules:
- Use strong action verbs (Developed, Implemented, Completed, Demonstrated...)
- Be specific: include tool names, versions, scores when available
- Keep bullets concise (1 line each)
- Use the candidate's existing CV style and language as reference
- For in-progress items, phrase as "Currently studying..." or "In progress:"
- Do NOT invent achievements — only reflect what was actually done
- Return ONLY valid JSON, no other text"""


def generate_cv_updates(cv_text: str, user_memory: UserMemory) -> dict:
    """
    Analyse the user's progress and return suggested CV updates.

    Returns:
        {
          "new_skills":        [str],   # bullets for Skills section
          "new_courses":       [str],   # certifications / courses done
          "in_progress":       [str],   # currently studying
          "updated_summary":   str,     # suggested professional summary tweak
          "full_skills_block": str,     # ready-to-paste Skills section
        }
    """
    completed_skills  = user_memory.skills.get("completed", [])
    in_progress       = user_memory.skills.get("learning", [])
    completed_courses = [c for c in user_memory.get_courses() if c.get("completed")]
    pending_courses   = [c for c in user_memory.get_courses() if not c.get("completed")]
    mentor_notes      = user_memory.data.get("mentor_notes", [])[-3:]
    today             = datetime.utcnow().strftime("%B %Y")

    # Build progress summary for the prompt
    progress_parts = []

    if completed_skills:
        lines = []
        for s in completed_skills:
            score = s.get("score", "")
            score_str = f" (validated {score}/100)" if score else " (validated)"
            lines.append(f"  - {s['name']}{score_str}, completed {s.get('completed_at', '')[:10]}")
        progress_parts.append("VALIDATED SKILLS (quiz-tested):\n" + "\n".join(lines))

    if completed_courses:
        lines = [f"  - {c['name']} ({c['skill']}) — {c.get('completed_at', '')[:10]}" for c in completed_courses]
        progress_parts.append("COMPLETED COURSES:\n" + "\n".join(lines))

    if in_progress:
        lines = [f"  - {s['name']} (level: {s.get('level', 'beginner')})" for s in in_progress]
        progress_parts.append("CURRENTLY STUDYING:\n" + "\n".join(lines))

    if pending_courses:
        lines = [f"  - {c['name']} ({c['skill']})" for c in pending_courses[:3]]
        progress_parts.append("ENROLLED COURSES (in progress):\n" + "\n".join(lines))

    if not progress_parts:
        return {
            "new_skills": [],
            "new_courses": [],
            "in_progress": [],
            "updated_summary": "",
            "full_skills_block": "",
            "nothing_yet": True,
        }

    progress_text = "\n\n".join(progress_parts)

    prompt = f"""Here is the candidate's current CV:

{cv_text}

---

Since writing this CV, the candidate has made the following progress (as of {today}):

{progress_text}

Generate CV update suggestions. Return ONLY this JSON:
{{
  "new_skills": [
    "Python — intermediate (2 years) + Databricks fundamentals (self-study, {today})"
  ],
  "new_courses": [
    "Microsoft Azure Databricks Data Engineering — Microsoft Learn ({today})"
  ],
  "in_progress": [
    "Currently studying: Advanced Cloud Data Platforms (Azure Synapse, Databricks)"
  ],
  "updated_summary": "One sentence to append or replace in the professional summary reflecting new skills",
  "full_skills_block": "Ready-to-paste updated SKILLS section for the CV"
}}

Be specific. Use the candidate's existing CV language style. Only include items from the progress above."""

    raw = chat_single(
        prompt=prompt,
        system=SYSTEM,
        model=LOCAL_MODEL,
        max_tokens=2048,
        temperature=0.2,
    )

    # Extract JSON
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass

    return {"raw": raw}
