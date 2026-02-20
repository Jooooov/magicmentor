"""
Memory Consolidator  (Perplexity sonar — cheapest model)
=========================================================
Runs in background after each session to extract and consolidate facts.
Uses the cheapest sonar model ($1/$1) — no web search needed for extraction.

Pattern: Two-Phase Background Memory (Mem0/LangMem, Feb 2026)
  - Zero latency on user-facing responses
  - 26% accuracy improvement vs naive context injection
  - 90%+ token savings
"""

import json
from datetime import datetime

from ..ai_client import chat_single, SONAR
from .persistent_memory import UserMemory

EXTRACTOR_SYSTEM = """You are a memory extraction specialist for a career mentoring AI.
Extract the most important, durable facts from a conversation for future sessions.

Focus on: career goals, skills learned, preferences, breakthroughs, blockers, job interests.
Ignore: greetings, generic questions, temporary states ("tired today").
Return only truly valuable, lasting facts."""


def extract_and_consolidate(
    conversation_history: list,
    session_type: str,
    user_memory: UserMemory,
) -> dict:
    """Extract facts from a session and merge into persistent memory."""

    if not conversation_history or len(conversation_history) < 2:
        return {"facts": [], "summary": "", "notes": []}

    # Serialize last 20 messages
    convo_text = ""
    for msg in conversation_history[-20:]:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if isinstance(content, str) and role in ("user", "assistant"):
            convo_text += f"{role.upper()}: {content[:500]}\n"

    current_profile = json.dumps(user_memory.data.get("profile", {}), indent=2)

    prompt = f"""Extract memory-worthy facts from this {session_type} session.

Current user profile (already known — don't repeat these):
{current_profile}

Conversation:
{convo_text}

Return ONLY this JSON:
{{
    "new_facts": [
        {{"fact": "User wants to transition to ML engineering within 12 months", "category": "career_goal", "confidence": "high"}}
    ],
    "profile_updates": {{
        "target_role": "ML Engineer"
    }},
    "session_summary": "One sentence summary of this session",
    "mentor_note": "One insight about this user worth noting for future sessions"
}}

If nothing new was learned, return empty arrays/objects."""

    try:
        response_text = chat_single(
            prompt=prompt,
            system=EXTRACTOR_SYSTEM,
            model=SONAR,       # cheapest — just extraction, no web search needed
            max_tokens=1024,
            temperature=0.1,
        )

        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start < 0 or end <= start:
            return {"facts": [], "summary": "", "notes": []}

        result = json.loads(response_text[start:end])

        # Apply to memory
        facts = result.get("new_facts", [])
        profile_updates = result.get("profile_updates", {})
        session_summary = result.get("session_summary", "")
        mentor_note = result.get("mentor_note", "")

        if profile_updates:
            for key in ("career_goals", "concerns", "preferred_topics"):
                if key in profile_updates and isinstance(profile_updates[key], list):
                    existing = user_memory.data.get("preferences", {}).get(key, [])
                    user_memory._data.setdefault("preferences", {})[key] = list(set(existing + profile_updates[key]))
                    del profile_updates[key]
            user_memory.update_profile(profile_updates)

        if mentor_note:
            user_memory.add_mentor_note(mentor_note)

        if session_summary:
            key_insights = [f["fact"] for f in facts if f.get("confidence") == "high"]
            user_memory.add_session_summary(session_type, session_summary, key_insights)

        for fact in facts:
            user_memory.log_event("extracted_fact", f"[{fact.get('category', 'general')}] {fact.get('fact', '')}")

        user_memory.save()
        return {"facts": facts, "summary": session_summary, "notes": [mentor_note] if mentor_note else []}

    except Exception as e:
        print(f"[consolidator] Error: {e}")
        return {"facts": [], "summary": "", "notes": [], "error": str(e)}


def consolidate_after_session(
    conversation_history: list,
    session_type: str,
    user_memory: UserMemory,
    run_async: bool = True,
) -> None:
    """Entry point. Runs in background thread by default (zero latency)."""
    if run_async:
        import threading
        threading.Thread(
            target=extract_and_consolidate,
            args=(conversation_history, session_type, user_memory),
            daemon=True,
        ).start()
        print("[consolidator] Memory consolidation running in background...")
    else:
        result = extract_and_consolidate(conversation_history, session_type, user_memory)
        print(f"[consolidator] Extracted {len(result.get('facts', []))} new facts")
        return result
