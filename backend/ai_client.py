"""
AI Client — Dual routing: MLX local (free) + Perplexity (web search only)
==========================================================================
Routing strategy:
  LOCAL (MLX / Qwen3-8B-4bit) → FREE, Apple Silicon, for:
    - CV parsing           (text extraction, no web needed)
    - Memory consolidation (fact extraction from conversation)
    - Learning Q&A         (Socratic teaching)
    - Job match scoring    (scoring logic)

  PERPLEXITY (sonar-pro) → paid, ONLY when live web search is needed:
    - Market insights      (current salaries, hot skills 2025/2026)
    - Job search fallback  (when jobspy returns 0 results)

Start MLX server before running:
  mlx_lm.server --model ~/Desktop/apps/MLX/Qwen3-8B-4bit --port 8080
"""

from openai import OpenAI
from .config import settings

# ── Model aliases ────────────────────────────────────────────────────
LOCAL_MODEL  = settings.LOCAL_MODEL    # "qwen3-8b-4bit"
SONAR_PRO    = "sonar-pro"             # Perplexity — web search tasks only

# Backwards-compat aliases (used across codebase — all now route to local)
SONAR        = LOCAL_MODEL
SONAR_REASON = LOCAL_MODEL

_local_client:      OpenAI | None = None
_perplexity_client: OpenAI | None = None


def _get_local() -> OpenAI:
    """MLX LM server — OpenAI-compatible API on localhost:8080."""
    global _local_client
    if _local_client is None:
        _local_client = OpenAI(
            api_key="local",
            base_url=settings.LOCAL_BASE_URL,
        )
    return _local_client


def _get_perplexity() -> OpenAI:
    """Perplexity API — only for tasks that need live web search."""
    global _perplexity_client
    if _perplexity_client is None:
        _perplexity_client = OpenAI(
            api_key=settings.PERPLEXITY_API_KEY,
            base_url="https://api.perplexity.ai",
        )
    return _perplexity_client


def _is_perplexity_model(model: str) -> bool:
    return model in ("sonar", "sonar-pro", "sonar-reasoning-pro")


def chat(
    messages: list[dict],
    model: str = LOCAL_MODEL,
    system: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> str:
    """
    Route to local MLX or Perplexity depending on model.

    Pass model=SONAR_PRO explicitly when web search is needed.
    Everything else is routed to local MLX (free).
    """
    full_messages = []
    if system:
        full_messages.append({"role": "system", "content": system})
    full_messages.extend(messages)

    if _is_perplexity_model(model):
        client = _get_perplexity()
        print(f"[ai] → Perplexity {model} (web search)")
    else:
        client = _get_local()
        print(f"[ai] → Local MLX {model} (free)")

    response = client.chat.completions.create(
        model=model,
        messages=full_messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content or ""


def chat_single(
    prompt: str,
    system: str = "",
    model: str = LOCAL_MODEL,
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> str:
    """Convenience wrapper for a single user turn."""
    return chat(
        messages=[{"role": "user", "content": prompt}],
        model=model,
        system=system,
        max_tokens=max_tokens,
        temperature=temperature,
    )
