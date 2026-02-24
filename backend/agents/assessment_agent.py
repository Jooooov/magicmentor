"""
Assessment Agent
================
Runs adaptive diagnostic knowledge quizzes (8-12 questions) to identify
knowledge gaps. Stores results in persistent memory, feeding them into
the learning flow as targeted study topics.

Topics: SQL, Microsoft Fabric, Power BI/DAX, Python Data, Azure/Cloud,
        Databricks, ETL/Data Engineering.
"""

import json

from ..ai_client import chat, LOCAL_MODEL
from ..memory.persistent_memory import UserMemory


ASSESSMENT_TOPICS = [
    {
        "label": "SQL",
        "subtopics": ["JOINs", "Window Functions", "CTEs", "Indexes", "Query Optimisation"],
    },
    {
        "label": "Microsoft Fabric",
        "subtopics": ["Lakehouses", "Pipelines", "Dataflows Gen2", "OneLake", "Semantic Models"],
    },
    {
        "label": "Power BI / DAX",
        "subtopics": ["measures", "CALCULATE", "filter context", "time intelligence"],
    },
    {
        "label": "Python Data",
        "subtopics": ["Pandas", "Polars", "generators", "type hints"],
    },
    {
        "label": "Azure / Cloud",
        "subtopics": ["ADF", "Synapse", "Blob Storage", "RBAC", "Key Vault"],
    },
    {
        "label": "Databricks",
        "subtopics": ["Delta Lake", "Spark", "Unity Catalog", "Medallion Architecture"],
    },
    {
        "label": "ETL / Data Engineering",
        "subtopics": ["SCD types", "idempotency", "schema evolution"],
    },
]


ASSESSOR_SYSTEM = """You are MagicMentor's Knowledge Assessor — a fast, decisive diagnostic interviewer.
Your job: run a crisp 8-question quiz covering all subtopics, then emit final results.

STRICT RULES — follow exactly:
1. ONE question per subtopic — ask it, get the answer, MOVE ON. Never follow up on the same subtopic.
2. After EVERY user answer, emit [QUESTION_SCORE: XX/100] on its own line, then immediately ask the next question on a NEW subtopic.
3. After all subtopics are covered (question 8+), emit the FINAL markers and stop.
4. Vary question types: conceptual (define/explain), practical (write code/query), design (choose approach).
5. Adapt difficulty: go harder if correct, easier if wrong — but still only 1 question per subtopic.
6. Feedback per answer: 1 line max. Be direct. Never hint at the answer before the user responds.
7. If the user flags [LOW_CONFIDENCE]: give score 25/100 for that subtopic, say "Noted — we'll add this to your study plan", then move on immediately.

AFTER EVERY USER ANSWER (mandatory, on its own line):
[QUESTION_SCORE: XX/100]

FINAL RESPONSE ONLY (after question 8, once all subtopics are covered):
[ASSESSMENT_SCORE: XX/100]
[SUBTOPIC_SCORES: {"SubtopicA": 85, "SubtopicB": 40, "SubtopicC": 70}]
[GAPS: ["SubtopicB: reason why it needs work"]]
[ASSESSMENT_COMPLETE]

Marker rules:
- QUESTION_SCORE: integer 0-100 based on correctness/depth of the answer
- ASSESSMENT_SCORE: overall weighted score 0-100
- SUBTOPIC_SCORES: valid JSON, one entry per subtopic
- GAPS: valid JSON array, only subtopics scored below 70
- NEVER emit [ASSESSMENT_COMPLETE] before covering all subtopics"""


def _strip_think(text: str) -> str:
    """Remove <think>...</think> block emitted by Qwen3. Returns content after it."""
    if "</think>" in text:
        return text.split("</think>", 1)[1].strip()
    if "<think>" in text:
        # think block not closed — drop everything inside
        return text.split("<think>", 1)[0].strip()
    return text


def _extract_bracketed_json(text: str, marker: str):
    """
    Extract JSON from a bracket-delimited marker like [MARKER: {...}] or [MARKER: [...]].
    Uses bracket-depth counting to handle nested structures correctly.
    Returns parsed Python object or None.
    """
    if marker not in text:
        return None
    after = text.split(marker, 1)[1].lstrip()
    if not after:
        return None
    first_char = after[0]
    if first_char not in "{[":
        return None
    open_ch  = first_char
    close_ch = "}" if open_ch == "{" else "]"
    depth    = 0
    end_idx  = None
    for i, ch in enumerate(after):
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                end_idx = i + 1
                break
    if end_idx is None:
        return None
    try:
        return json.loads(after[:end_idx])
    except json.JSONDecodeError:
        return None


def start_assessment(topic: dict, user_memory: UserMemory = None) -> dict:
    """
    Start a knowledge diagnostic assessment for the given topic.

    Args:
        topic: dict from ASSESSMENT_TOPICS, e.g. {"label": "SQL", "subtopics": [...]}
        user_memory: UserMemory instance for personalisation

    Returns:
        {"message": str, "history": list, "skill": str, "complete": False}
    """
    memory_context = user_memory.build_context_prompt() if user_memory else ""
    system = ASSESSOR_SYSTEM
    if memory_context:
        system += f"\n\n{memory_context}"

    subtopics_str = ", ".join(topic["subtopics"])

    prompt = (
        f"Let's run a diagnostic assessment on: {topic['label']}\n"
        f"Subtopics to cover: {subtopics_str}\n\n"
        "Start the quiz now. In one sentence introduce the assessment and say "
        "how many questions to expect, then ask your first question.\n"
        "Do NOT emit any [ASSESSMENT_*] markers yet — those come only at the end."
    )

    response_text = chat(
        messages=[{"role": "user", "content": prompt}],
        model=LOCAL_MODEL,
        system=system,
        max_tokens=512,
        temperature=0.4,
    )

    clean_response = _strip_think(response_text)

    history = [
        {"role": "user",      "content": prompt},
        {"role": "assistant", "content": clean_response},
    ]

    return {
        "message":         clean_response,
        "history":         history,
        "skill":           topic["label"],
        "complete":        False,
        "score":           None,
        "subtopic_scores": {},
        "gaps":            [],
    }


def continue_assessment(
    user_input: str,
    history: list,
    skill: str,
    user_memory: UserMemory = None,
) -> dict:
    """
    Continue an active assessment session with a user answer.

    Returns:
        {
            "message":          str,
            "history":          list,
            "skill":            str,
            "complete":         bool,
            "score":            int | None,
            "subtopic_scores":  dict,
            "gaps":             list,
        }
    """
    messages = history.copy()
    messages.append({"role": "user", "content": user_input})

    response_text = chat(
        messages=messages,
        model=LOCAL_MODEL,
        system=ASSESSOR_SYSTEM,
        max_tokens=768,
        temperature=0.3,
    )

    # Strip Qwen3 <think> block before storing and parsing
    clean_response = _strip_think(response_text)
    messages.append({"role": "assistant", "content": clean_response})

    # ── Parse markers ──────────────────────────────────────────────────────────
    complete        = "[ASSESSMENT_COMPLETE]" in clean_response
    score           = None
    question_score  = None
    subtopic_scores = {}
    gaps            = []

    if "[QUESTION_SCORE:" in clean_response:
        try:
            qs_str = clean_response.split("[QUESTION_SCORE:")[1].split("]")[0]
            question_score = int(qs_str.strip().split("/")[0])
        except (IndexError, ValueError):
            pass

    if "[ASSESSMENT_SCORE:" in clean_response:
        try:
            score_str = clean_response.split("[ASSESSMENT_SCORE:")[1].split("]")[0]
            score = int(score_str.strip().split("/")[0])
        except (IndexError, ValueError):
            pass

    parsed_subtopics = _extract_bracketed_json(clean_response, "[SUBTOPIC_SCORES:")
    if isinstance(parsed_subtopics, dict):
        subtopic_scores = parsed_subtopics

    parsed_gaps = _extract_bracketed_json(clean_response, "[GAPS:")
    if isinstance(parsed_gaps, list):
        gaps = parsed_gaps

    return {
        "message":         clean_response,
        "history":         messages,
        "skill":           skill,
        "complete":        complete,
        "score":           score,
        "question_score":  question_score,
        "subtopic_scores": subtopic_scores,
        "gaps":            gaps,
    }


def build_gap_entries(
    skill: str,
    subtopic_scores: dict,
    gaps: list,
    overall_score: int,
) -> list:
    """
    Convert assessment output into canonical skill_gap dicts compatible
    with the mentor skill_gaps format (so _build_mentor_context works unchanged).

    Only creates entries for subtopics that scored < 70.
    """
    low_subtopics = {k: v for k, v in subtopic_scores.items() if v < 70}

    # Map gap description strings to their subtopics
    gap_reasons = {}
    for g in gaps:
        if isinstance(g, str):
            for sub in subtopic_scores.keys():
                if sub.lower() in g.lower():
                    gap_reasons[sub] = g
                    break

    entries = []
    priority = 1
    for subtopic, sub_score in sorted(low_subtopics.items(), key=lambda x: x[1]):
        reason = gap_reasons.get(subtopic, f"Scored {sub_score}/100 in {subtopic}")
        entries.append({
            "skill":                   f"{skill} — {subtopic}",
            "priority":                priority,
            "category":                skill.lower().replace(" / ", "_").replace(" ", "_"),
            "reason":                  reason,
            "builds_on":               f"Existing {skill} knowledge",
            "estimated_learning_time": "1-2 weeks",
            "job_market_demand":       "high" if overall_score < 50 else "medium",
            "resources":               [],
            "source":                  "assessment",
            "assessed_score":          sub_score,
        })
        priority += 1

    return entries
