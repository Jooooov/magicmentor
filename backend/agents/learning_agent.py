"""
Learning Agent  (Perplexity sonar-reasoning-pro)
=================================================
sonar-reasoning-pro uses chain-of-thought reasoning (DeepSeek-R1 1776 based).
Perfect for Socratic teaching — it thinks step-by-step before answering.

Also has web search: can look up current best practices and real code examples.

Cost: $2/$8 per 1M tokens (vs Opus $5/$25 — 60% cheaper on input, 68% cheaper on output)
"""

import json

from ..ai_client import chat, SONAR_REASON, SONAR_PRO
from ..memory.persistent_memory import UserMemory

TUTOR_SYSTEM = """You are MagicMentor's Learning Coach — a skilled Socratic tutor with web search.

Teaching method (follow this cycle):
1. EXPLAIN: Clear, concise explanation (2-3 paragraphs max)
2. EXAMPLE: Real-world, runnable code example (use your web search for current best practices)
3. QUESTION: One targeted question to test understanding
4. VALIDATE: Assess the answer, give feedback, correct misconceptions
5. ADVANCE: Move forward only when understanding is confirmed

Rules:
- Connect new concepts to what the learner already knows
- Use analogies from their background (check their profile if available)
- After every 3-4 concepts, run a mini-quiz
- Be encouraging but honest about gaps
- Connect everything to real job scenarios and interviews
- Look up current documentation and best practices with your web search
- Code examples should be practical and reflect 2025/2026 standards

After a quiz, include score as: [QUIZ_SCORE: XX/100]
When session is truly complete (all core concepts covered + validated): [SESSION_COMPLETE]"""


def start_learning_session(
    skill_name: str,
    user_level: str = "beginner",
    user_memory: UserMemory = None,
    context: str = "",
) -> dict:
    """Initialise a new Socratic learning session."""
    memory_context = user_memory.build_context_prompt() if user_memory else ""

    system = TUTOR_SYSTEM
    if memory_context:
        system += f"\n\n{memory_context}"

    background = context or (f"Learner background: {memory_context[:200]}" if memory_context else "")

    prompt = f"""Let's learn: {skill_name}
Learner's current level: {user_level}
{background}

Search for the most current version and best practices for {skill_name} first.
Then:
1. Give a 2-sentence overview of what we'll cover and why it matters for their career
2. Start with the first core concept with a real code example
3. Ask one question to gauge their starting knowledge"""

    response_text = chat(
        messages=[{"role": "user", "content": prompt}],
        model=SONAR_REASON,
        system=system,
        max_tokens=2048,
        temperature=0.3,
    )

    history = [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": response_text},
    ]

    # Track in memory
    if user_memory:
        learning = user_memory._data["skills"]["learning"]
        if not any(s.get("name") == skill_name for s in learning):
            learning.append({"name": skill_name, "level": user_level})
            user_memory.save()

    return {
        "message": response_text,
        "history": history,
        "skill": skill_name,
        "quiz_score": None,
        "session_complete": False,
    }


def continue_learning(
    user_response: str,
    conversation_history: list,
    skill_name: str,
    user_memory: UserMemory = None,
) -> dict:
    """Continue an active learning session."""
    messages = conversation_history.copy()
    messages.append({"role": "user", "content": user_response})

    response_text = chat(
        messages=messages,
        model=SONAR_REASON,
        system=TUTOR_SYSTEM,
        max_tokens=2048,
        temperature=0.3,
    )

    # Parse quiz score
    quiz_score = None
    if "[QUIZ_SCORE:" in response_text:
        try:
            score_str = response_text.split("[QUIZ_SCORE:")[1].split("]")[0]
            quiz_score = int(score_str.split("/")[0].strip())
        except (IndexError, ValueError):
            pass

    session_complete = "[SESSION_COMPLETE]" in response_text
    messages.append({"role": "assistant", "content": response_text})

    if user_memory and quiz_score and quiz_score >= 70 and session_complete:
        user_memory.mark_skill_completed(skill_name, quiz_score)
        user_memory.add_session_summary(
            session_type="learning",
            summary=f"Completed {skill_name}. Score: {quiz_score}/100",
            key_insights=[f"{skill_name} validated at {quiz_score}/100"],
        )

    return {
        "message": response_text,
        "history": messages,
        "skill": skill_name,
        "quiz_score": quiz_score,
        "session_complete": session_complete,
    }


def run_final_validation(
    skill_name: str,
    conversation_history: list,
    user_memory: UserMemory = None,
) -> dict:
    """Run a comprehensive final validation quiz."""
    messages = conversation_history.copy()

    validation_prompt = f"""Run a comprehensive 5-question validation quiz for {skill_name}.
Use your web search to make the questions reflect CURRENT best practices and common interview questions.

After all 5 answers, provide:
- Overall score out of 100
- Areas of strength
- Areas needing more work
- Whether ready to list on CV / use in a job interview

Format final result as:
[FINAL_SCORE: XX/100]
[READY_FOR_CV: yes/no]"""

    messages.append({"role": "user", "content": validation_prompt})

    response_text = chat(
        messages=messages,
        model=SONAR_REASON,
        system=TUTOR_SYSTEM,
        max_tokens=3000,
        temperature=0.2,
    )

    final_score = None
    ready_for_cv = False
    if "[FINAL_SCORE:" in response_text:
        try:
            score_str = response_text.split("[FINAL_SCORE:")[1].split("]")[0]
            final_score = int(score_str.split("/")[0].strip())
        except (IndexError, ValueError):
            pass
    if "[READY_FOR_CV: yes]" in response_text.lower():
        ready_for_cv = True

    if user_memory and final_score:
        user_memory.mark_skill_completed(skill_name, final_score)
        user_memory.add_session_summary(
            session_type="validation",
            summary=f"Validated {skill_name}. Score: {final_score}/100. CV ready: {ready_for_cv}",
        )

    return {
        "message": response_text,
        "history": messages + [{"role": "assistant", "content": response_text}],
        "final_score": final_score,
        "ready_for_cv": ready_for_cv,
    }
