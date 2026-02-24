"""MagicMentor — Streamlit web app (Farm Rio aesthetic, mobile-first)"""

import os
import sys
import re
import urllib.request
from pathlib import Path
from datetime import datetime

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# ── Streamlit must be imported before any st.* calls ─────────────────────────
import streamlit as st

st.set_page_config(
    page_title="MagicMentor 🌺",
    page_icon="🌺",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Backend imports ───────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from backend.memory.persistent_memory import get_user_memory
from backend.agents.assessment_agent import (
    start_assessment,
    continue_assessment,
    build_gap_entries,
    ASSESSMENT_TOPICS,
)
from backend.agents.mentor_agent import chat_with_mentor
from backend.parsers.cv_parser import extract_text_from_pdf

# ── Farm Rio CSS ──────────────────────────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap');

:root {
    --coral:    #FF6B35;
    --gold:     #FFD700;
    --green:    #2ECC71;
    --pink:     #FF6EB4;
    --purple:   #9B59B6;
    --teal:     #00BFA5;
    --orange:   #FF8C42;
    --cream:    #FFF8F0;
    --leaf:     #4CAF50;
}

/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }

/* Tropical gradient background */
body, .stApp {
    background: linear-gradient(135deg,
        #FFF0E6 0%,
        #FFF8F0 25%,
        #F0FFF4 50%,
        #FFF0F8 75%,
        #FFF8E1 100%) !important;
    background-attachment: fixed !important;
    font-family: 'Nunito', sans-serif !important;
}

/* Decorative top bar */
.stApp::before {
    content: '';
    display: block;
    height: 5px;
    background: linear-gradient(90deg,
        var(--coral), var(--gold), var(--green),
        var(--pink), var(--teal), var(--coral));
    position: fixed;
    top: 0; left: 0; right: 0;
    z-index: 9999;
}

/* Cards */
.mm-card {
    background: rgba(255,255,255,0.82);
    backdrop-filter: blur(6px);
    border-radius: 20px;
    border: 1.5px solid rgba(255,107,53,0.12);
    box-shadow: 0 4px 24px rgba(255,107,53,0.08);
    padding: 1.1rem 1.3rem;
    margin: 0.5rem 0;
}

/* Quiz question card — tropical highlight */
.mm-card-question {
    background: linear-gradient(135deg, rgba(255,255,255,0.95), rgba(255,240,230,0.6));
    backdrop-filter: blur(6px);
    border-radius: 20px;
    border-left: 4px solid var(--coral);
    box-shadow: 0 4px 24px rgba(255,107,53,0.12);
    padding: 1.2rem 1.4rem;
    margin: 0.5rem 0;
    font-size: 1.05rem;
    line-height: 1.6;
}

/* Score badge */
.q-score-badge {
    display: inline-block;
    padding: 4px 16px;
    border-radius: 30px;
    font-size: 1rem;
    font-weight: 800;
    margin: 0.5rem 0;
}
.q-score-high   { background: #E8F8F0; color: #1E8449; border: 2px solid #2ECC71; }
.q-score-mid    { background: #FEF9E7; color: #B7950B; border: 2px solid #F4D03F; }
.q-score-low    { background: #FDEDEC; color: #C0392B; border: 2px solid #E74C3C; }
.q-score-flag   { background: #EEF2FF; color: #5B6EAE; border: 2px solid #9B59B6; }

/* Low confidence flag pill */
.low-conf-pill {
    display: inline-block;
    background: linear-gradient(90deg, #9B59B6, #8E44AD);
    color: white;
    padding: 3px 12px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 700;
    margin-left: 8px;
}

/* Skill tags */
.mm-tag {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
    margin: 2px 3px;
    color: white;
}
.mm-tag-coral  { background: var(--coral); }
.mm-tag-purple { background: var(--purple); }
.mm-tag-green  { background: var(--green); }
.mm-tag-pink   { background: var(--pink); }
.mm-tag-gold   { background: #C9A800; }
.mm-tag-teal   { background: var(--teal); }

/* Primary buttons — coral pill */
.stButton > button {
    background: linear-gradient(135deg, var(--coral), var(--orange)) !important;
    color: white !important;
    border: none !important;
    border-radius: 30px !important;
    font-weight: 700 !important;
    width: 100% !important;
    padding: 0.55rem 1rem !important;
    transition: all 0.2s;
    box-shadow: 0 3px 12px rgba(255,107,53,0.25) !important;
}
.stButton > button:hover {
    opacity: 0.88;
    box-shadow: 0 5px 18px rgba(255,107,53,0.35) !important;
    transform: translateY(-1px);
}
.stButton > button:disabled {
    background: #ddd !important;
    color: #999 !important;
    box-shadow: none !important;
}

/* "Não me sinto confiante" button — purple ghost */
.btn-lowconf .stButton > button {
    background: linear-gradient(135deg, #9B59B6, #8E44AD) !important;
    box-shadow: 0 3px 12px rgba(155,89,182,0.25) !important;
    font-size: 0.88rem !important;
}
.btn-lowconf .stButton > button:hover {
    box-shadow: 0 5px 18px rgba(155,89,182,0.35) !important;
}

/* Bottom nav bar */
[data-testid="stBottom"] { display: none; }

.nav-bar-wrap {
    position: fixed;
    bottom: 0; left: 0; right: 0;
    background: rgba(255,255,255,0.92);
    backdrop-filter: blur(10px);
    border-top: 2px solid rgba(255,107,53,0.15);
    padding: 6px 8px 12px;
    z-index: 1000;
}
.nav-bar-wrap .stButton > button {
    background: transparent !important;
    color: #666 !important;
    border-radius: 10px !important;
    font-size: 0.68rem !important;
    padding: 4px 2px !important;
    box-shadow: none !important;
    border: none !important;
    font-weight: 700 !important;
}
.nav-bar-wrap .stButton > button:hover {
    background: rgba(255,107,53,0.08) !important;
    color: var(--coral) !important;
    opacity: 1 !important;
    transform: none;
}

/* Push content up so fixed nav doesn't overlap */
.main .block-container { padding-bottom: 110px !important; padding-top: 1.5rem !important; }

/* Score colours */
.score-high { color: var(--green);  font-weight: 700; }
.score-mid  { color: #C9A800;       font-weight: 700; }
.score-low  { color: #E74C3C;       font-weight: 700; }

h1 { color: var(--coral); font-weight: 800; }
h2, h3 { color: #444; }

/* Progress bar tropical */
.stProgress > div > div { background: linear-gradient(90deg, var(--coral), var(--gold)) !important; }
</style>
"""


def _inject_css():
    st.markdown(_CSS, unsafe_allow_html=True)


# ── Session-state defaults ────────────────────────────────────────────────────
_DEFAULTS: dict = {
    "page":           "welcome",
    "mem":            None,
    "cv_text":        "",
    "analysis":       {},
    "chat_history":   [],
    # Assessment state machine
    "quiz_state":      "selecting",
    "quiz_topic":      None,
    "quiz_history":    [],
    "quiz_skill":      "",
    "quiz_score":      None,
    "quiz_subtopics":  {},
    "quiz_gaps":       [],
    "quiz_q_count":    0,
    "quiz_last_q_score": None,   # score for the last answered question
    "quiz_low_conf":   [],        # list of subtopics flagged as low confidence
    # MLX server status (None = unchecked)
    "mlx_ok":         None,
}


def _init_state():
    for k, v in _DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # Load user memory once
    if st.session_state["mem"] is None:
        with st.spinner("A carregar o teu perfil..."):
            st.session_state["mem"] = get_user_memory("JV")

    # Auto-detect CV PDF
    if not st.session_state["cv_text"]:
        jv_dir = ROOT / "data" / "users" / "JV"
        for pdf in sorted(jv_dir.glob("*.pdf")):
            try:
                text = extract_text_from_pdf(str(pdf))
                if text and len(text) > 100:
                    st.session_state["cv_text"] = text
                    break
            except Exception:
                pass


def _check_mlx():
    if st.session_state["mlx_ok"] is None:
        try:
            urllib.request.urlopen("http://localhost:8080/v1/models", timeout=2)
            st.session_state["mlx_ok"] = True
        except Exception:
            st.session_state["mlx_ok"] = False


# ── Routing helpers ───────────────────────────────────────────────────────────
def _nav(page: str):
    st.session_state["page"] = page
    st.rerun()


# ── Display helpers ───────────────────────────────────────────────────────────
def _score_cls(score: int) -> str:
    if score >= 75:
        return "score-high"
    if score >= 50:
        return "score-mid"
    return "score-low"


def _bar(score: int, width: int = 10) -> str:
    filled = round(score / 100 * width)
    return "█" * filled + "░" * (width - filled)


def _fmt_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso[:10])
        months = ["jan","fev","mar","abr","mai","jun","jul",
                  "ago","set","out","nov","dez"]
        return f"{dt.day} {months[dt.month - 1]}"
    except Exception:
        return iso[:10] if iso else ""


def _card(html: str):
    st.markdown(f'<div class="mm-card">{html}</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Welcome
# ══════════════════════════════════════════════════════════════════════════════
def page_welcome():
    mem = st.session_state["mem"]

    st.markdown("# 🌺 MagicMentor")

    # ── Stats card ──
    name             = mem.profile.get("name") or "Aventureiro"
    current_skills   = mem.skills.get("current", [])
    completed_skills = mem.skills.get("completed", [])
    courses          = mem.get_courses()
    done_courses     = [c for c in courses if c.get("completed")]
    assessments      = mem.get_assessment_history()

    _card(
        f"<h3>Olá, {name}! 👋</h3>"
        f"<p>"
        f"<b>{len(current_skills)}</b> skills actuais &nbsp;·&nbsp;"
        f"<b>{len(completed_skills)}</b> validadas &nbsp;·&nbsp;"
        f"<b>{len(done_courses)}</b> cursos concluídos &nbsp;·&nbsp;"
        f"<b>{len(assessments)}</b> diagnósticos"
        f"</p>"
    )

    if not st.session_state["mlx_ok"]:
        st.warning(
            "⚠️ Servidor MLX offline — Diagnóstico indisponível. "
            "Chat com mentor funciona."
        )

    # ── Quick-action buttons ──
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🧪\nDiagnóstico", key="w_assess"):
            _nav("assessment")
    with c2:
        if st.button("📈\nProgresso", key="w_prog"):
            _nav("progress")
    with c3:
        if st.button("💬\nMentor", key="w_chat"):
            _nav("chat")

    # ── Last mentor note ──
    notes = mem.data.get("mentor_notes", [])
    if notes:
        st.markdown("---\n#### 📝 Última nota do mentor")
        _card(notes[-1].get("note", ""))

    # ── Assessment gaps ──
    gaps = mem.get_assessment_gaps()
    if gaps:
        st.markdown("---\n#### ⚡ Lacunas identificadas")
        for g in gaps[:6]:
            skill  = g.get("skill", "")
            reason = g.get("reason", "")
            score  = g.get("assessed_score", 0)
            cls    = _score_cls(score)
            _card(
                f"⚡ <b>{skill}</b>"
                f"{' — ' + reason if reason else ''}"
                f" &nbsp;<span class='{cls}'>{score}/100</span>"
            )

    # ── Recent session summaries ──
    summaries = mem.data.get("session_summaries", [])
    if summaries:
        st.markdown("---\n#### 🗂 Sessões recentes")
        for s in list(reversed(summaries))[:3]:
            date    = _fmt_date(s.get("date", ""))
            stype   = s.get("type", "")
            summary = s.get("summary", "")[:130]
            _card(f"<small>{date} · {stype}</small><br>{summary}…")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Assessment
# ══════════════════════════════════════════════════════════════════════════════
def page_assessment():
    state = st.session_state["quiz_state"]
    if state == "selecting":
        _assess_selecting()
    elif state == "quizzing":
        _assess_quizzing()
    else:
        _assess_results()


# ── Selecting ─────────────────────────────────────────────────────────────────
def _assess_selecting():
    mem    = st.session_state["mem"]
    mlx_ok = bool(st.session_state.get("mlx_ok"))

    st.markdown("# 🧪 Diagnóstico de Conhecimentos")

    if not mlx_ok:
        st.warning("⚠️ Servidor MLX offline — inicie o servidor para usar diagnósticos.")

    # Topic grid (2 columns)
    topics = ASSESSMENT_TOPICS
    for i in range(0, len(topics), 2):
        cols = st.columns(2)
        for j, col in enumerate(cols):
            if i + j >= len(topics):
                break
            topic = topics[i + j]
            n_sub = len(topic.get("subtopics", []))
            with col:
                _card(
                    f"<b>{topic['label']}</b><br>"
                    f"<small>{n_sub} subtópicos</small>"
                )
                if st.button(
                    f"Começar",
                    key=f"start_{topic['label']}",
                    disabled=not mlx_ok,
                ):
                    with st.spinner(f"A preparar {topic['label']}..."):
                        result = start_assessment(topic, mem)
                    st.session_state.update({
                        "quiz_state":        "quizzing",
                        "quiz_topic":        topic,
                        "quiz_skill":        result["skill"],
                        "quiz_history":      result["history"],
                        "quiz_score":        None,
                        "quiz_subtopics":    {},
                        "quiz_gaps":         [],
                        "quiz_q_count":      1,
                        "quiz_last_q_score": None,
                        "quiz_low_conf":     [],
                    })
                    st.rerun()

    # Past assessments
    history = mem.get_assessment_history()
    if history:
        st.markdown("---\n#### Diagnósticos anteriores")
        for h in list(reversed(history))[:5]:
            skill = h.get("skill", "")
            score = h.get("overall_score", 0)
            date  = _fmt_date(h.get("assessed_at", ""))
            cls   = _score_cls(score)
            bar   = _bar(score)
            _card(
                f"<b>{skill}</b> &nbsp;"
                f"<span class='{cls}'>{score}/100</span> &nbsp;"
                f"<span style='font-family:monospace'>{bar}</span> &nbsp;"
                f"<small>{date}</small>"
            )


# ── Quizzing ──────────────────────────────────────────────────────────────────
def _assess_quizzing():
    skill    = st.session_state["quiz_skill"]
    q_count  = st.session_state["quiz_q_count"]
    history  = st.session_state["quiz_history"]
    last_qs  = st.session_state.get("quiz_last_q_score")
    low_conf = st.session_state.get("quiz_low_conf", [])

    st.markdown(f"# 🧪 {skill} · Pergunta {q_count}")
    st.progress(min(q_count / 8, 1.0))

    # ── Show score from previous answer ──────────────────────────────────────
    if last_qs is not None:
        if last_qs >= 70:
            badge_cls, icon = "q-score-high", "✅"
        elif last_qs >= 40:
            badge_cls, icon = "q-score-mid",  "🟡"
        else:
            badge_cls, icon = "q-score-low",  "🔴"
        st.markdown(
            f'<span class="q-score-badge {badge_cls}">{icon} Resposta anterior: {last_qs}/100</span>',
            unsafe_allow_html=True,
        )

    if low_conf:
        st.markdown(
            f'<small>📚 Marcados para estudo: '
            + "".join(f'<span class="low-conf-pill">{t}</span>' for t in low_conf)
            + "</small>",
            unsafe_allow_html=True,
        )

    # ── Find last assistant message & strip markers for display ──────────────
    last_q = ""
    for msg in reversed(history):
        if msg.get("role") == "assistant":
            last_q = msg.get("content", "")
            break

    display_q = re.sub(r"\[(?:ASSESSMENT|QUESTION)_[^\]]+\]", "", last_q).strip()
    # Strip any leftover <think> block from display (safety net)
    if "</think>" in display_q:
        display_q = display_q.split("</think>", 1)[1].strip()
    st.markdown('<div class="mm-card-question">', unsafe_allow_html=True)
    st.markdown(display_q)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Answer form ───────────────────────────────────────────────────────────
    with st.form("quiz_form", clear_on_submit=True):
        answer = st.text_area("A tua resposta:", height=120,
                              placeholder="Escreve aqui o que sabes...")
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            submitted = st.form_submit_button("✅ Submeter")
        with col2:
            low_conf_btn = st.form_submit_button("😅 Não me sinto confiante")
        with col3:
            exit_btn = st.form_submit_button("Sair")

    if exit_btn:
        st.session_state["quiz_state"] = "selecting"
        st.rerun()

    # ── Handle "não me sinto confiante" ──────────────────────────────────────
    if low_conf_btn:
        flag_text = (answer.strip() + "\n\n[LOW_CONFIDENCE]") if answer.strip() \
                    else "[LOW_CONFIDENCE] — não me sinto confiante neste tópico"
        with st.spinner("A registar... 🌺"):
            result = continue_assessment(
                flag_text,
                st.session_state["quiz_history"],
                skill,
                st.session_state["mem"],
            )
        st.session_state["quiz_history"]    = result["history"]
        st.session_state["quiz_q_count"]   += 1
        st.session_state["quiz_last_q_score"] = 25  # always low-conf score
        # Record which question number was flagged
        current_low = st.session_state.get("quiz_low_conf", [])
        current_low.append(f"Q{q_count}")
        st.session_state["quiz_low_conf"] = current_low
        if result.get("subtopic_scores"):
            st.session_state["quiz_subtopics"].update(result["subtopic_scores"])
        if result.get("gaps"):
            st.session_state["quiz_gaps"] = result["gaps"]
        if result.get("complete"):
            st.session_state["quiz_state"] = "results"
        st.rerun()

    # ── Handle normal submit ──────────────────────────────────────────────────
    if submitted and answer.strip():
        with st.spinner("A avaliar... 🌺"):
            result = continue_assessment(
                answer,
                st.session_state["quiz_history"],
                skill,
                st.session_state["mem"],
            )

        st.session_state["quiz_history"]       = result["history"]
        st.session_state["quiz_q_count"]      += 1
        st.session_state["quiz_last_q_score"]  = result.get("question_score")

        if result.get("score") is not None:
            st.session_state["quiz_score"] = result["score"]
        if result.get("subtopic_scores"):
            st.session_state["quiz_subtopics"].update(result["subtopic_scores"])
        if result.get("gaps"):
            st.session_state["quiz_gaps"] = result["gaps"]

        if result.get("complete"):
            st.session_state["quiz_state"] = "results"

        st.rerun()


# ── Results ───────────────────────────────────────────────────────────────────
def _assess_results():
    skill     = st.session_state["quiz_skill"]
    score     = st.session_state["quiz_score"] or 0
    subtopics = st.session_state["quiz_subtopics"]
    gaps      = st.session_state["quiz_gaps"]

    cls = _score_cls(score)
    st.markdown(f"# 🎯 {skill}")
    st.markdown(
        f'<div class="mm-card" style="text-align:center">'
        f'<span class="{cls}" style="font-size:3rem">{score}</span>'
        f'<span style="font-size:1.5rem">/100</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if subtopics:
        st.markdown("#### Sub-tópicos (pior → melhor)")
        for sub, sub_score in sorted(subtopics.items(), key=lambda x: x[1]):
            bar      = _bar(sub_score)
            sub_cls  = _score_cls(sub_score)
            gap_icon = " ⚡" if sub_score < 70 else ""
            _card(
                f"<b>{sub}</b> &nbsp;"
                f"<span style='font-family:monospace'>{bar}</span> &nbsp;"
                f"<span class='{sub_cls}'>{sub_score}</span>{gap_icon}"
            )

    # Show low-confidence flags if any
    low_conf = st.session_state.get("quiz_low_conf", [])
    if low_conf:
        st.markdown(
            f'<div class="mm-card">📚 <b>Marcados para estudo</b> (baixa confiança): '
            + "".join(f'<span class="low-conf-pill">{t}</span>' for t in low_conf)
            + "</div>",
            unsafe_allow_html=True,
        )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Guardar resultados"):
            mem         = st.session_state["mem"]
            gap_entries = build_gap_entries(skill, subtopics, gaps, score)
            mem.save_assessment(skill, score, subtopics, gap_entries)
            mem.add_session_summary(
                "assessment",
                f"Diagnóstico de {skill}: {score}/100",
                [f"Score: {score}/100",
                 f"{len(gap_entries)} lacunas identificadas"],
            )
            st.toast(f"✅ Diagnóstico de {skill} guardado!", icon="🌺")
            st.session_state["quiz_state"] = "selecting"
            st.rerun()
    with col2:
        if st.button("📈 Ver Progresso"):
            _nav("progress")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Progress
# ══════════════════════════════════════════════════════════════════════════════
def page_progress():
    mem = st.session_state["mem"]
    st.markdown("# 📈 O Teu Progresso")

    # Current skills
    current = mem.skills.get("current", [])
    if current:
        st.markdown("#### Skills actuais")
        tags = "".join(
            f'<span class="mm-tag mm-tag-coral">{s["name"]}</span>'
            for s in current
        )
        _card(tags)

    # Validated / completed skills
    completed = mem.skills.get("completed", [])
    if completed:
        st.markdown("#### Skills validadas")
        for s in completed:
            name = s.get("name", "")
            sc   = s.get("score", 0)
            st.markdown(f"✓ **{name}**")
            st.progress(sc / 100, text=f"{sc}/100")

    # Active learning sessions
    sessions = mem.list_active_sessions()
    if sessions:
        st.markdown("#### Sessões em progresso")
        for sess in sessions:
            sk    = sess.get("skill", "")
            turns = len(sess.get("history", []))
            date  = _fmt_date(sess.get("last_updated", ""))
            _card(f"↩ <b>{sk}</b> — {turns} trocas · pausado {date}")

    # Assessment history
    history = mem.get_assessment_history()
    if history:
        st.markdown("#### Diagnósticos")
        for h in reversed(history):
            skill = h.get("skill", "")
            score = h.get("overall_score", 0)
            date  = _fmt_date(h.get("assessed_at", ""))
            bar   = _bar(score)
            cls   = _score_cls(score)
            with st.expander(f"{skill} — {score}/100 · {date}"):
                subs = h.get("subtopic_scores", {})
                if subs:
                    for sub, sub_sc in sorted(subs.items(), key=lambda x: x[1]):
                        sub_cls = _score_cls(sub_sc)
                        st.markdown(
                            f'<span class="{sub_cls}">●</span> **{sub}**: {sub_sc}/100',
                            unsafe_allow_html=True,
                        )
                else:
                    st.caption("Sem detalhe de sub-tópicos.")
            st.progress(score / 100,
                        text=f"{bar}  {score}/100 · {date}")

    # Courses
    courses     = mem.get_courses()
    todo        = [c for c in courses if not c.get("completed")]
    done        = [c for c in courses if c.get("completed")]

    if courses:
        st.markdown("#### Cursos")

        if todo:
            st.markdown("**Para fazer:**")
            for c in todo:
                name = c.get("name", "")
                url  = c.get("url", "")
                free = "FREE" if c.get("free") else "PAGO"
                tag_cls = "mm-tag-green" if c.get("free") else "mm-tag-gold"
                cols = st.columns([5, 1])
                with cols[0]:
                    _card(
                        f'<span class="mm-tag {tag_cls}">{free}</span> {name}'
                    )
                with cols[1]:
                    if url:
                        st.link_button("🔗", url)

        if done:
            st.markdown("**Concluídos:**")
            for c in done:
                name = c.get("name", "")
                date = _fmt_date(c.get("completed_at", ""))
                _card(f"✓ {name} <small>— {date}</small>")

        # Mark a course done
        if todo:
            st.markdown("---")
            names = [c.get("name", f"Curso {i}") for i, c in enumerate(todo)]
            sel   = st.selectbox("Marcar como concluído:", names)
            if st.button("✅ Marcar concluído"):
                idx      = names.index(sel)
                full_idx = courses.index(todo[idx])
                mem.mark_course_done(full_idx)
                st.toast(f"✅ {sel} marcado como concluído!", icon="🌺")
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Chat
# ══════════════════════════════════════════════════════════════════════════════
def page_chat():
    mem = st.session_state["mem"]
    st.markdown("# 💬 Chat com o Mentor")

    # Seed welcome message
    if not st.session_state["chat_history"]:
        name    = mem.profile.get("name") or "Aventureiro"
        welcome = (
            f"Olá, {name}! 🌺 Sou o teu mentor de aprendizagem. "
            "Estou aqui para te ajudar a planear o teu desenvolvimento, "
            "analisar as tuas lacunas e orientar os teus próximos passos. "
            "O que queres trabalhar hoje?"
        )
        st.session_state["chat_history"] = [
            {"role": "assistant", "content": welcome}
        ]

    # Render history
    for msg in st.session_state["chat_history"]:
        avatar = "🌺" if msg["role"] == "assistant" else None
        with st.chat_message(msg["role"], avatar=avatar):
            st.write(msg["content"])

    # User input
    if prompt := st.chat_input("Fala com o teu mentor..."):
        # Show user message immediately
        with st.chat_message("user"):
            st.write(prompt)

        # Build history without current message
        prior_history = list(st.session_state["chat_history"])

        with st.spinner("Mentor a pensar... 🌺"):
            result = chat_with_mentor(
                prompt,
                prior_history,
                user_memory=mem,
            )

        st.session_state["chat_history"] = result["history"]

        if result.get("mentor_note"):
            mem.add_mentor_note(result["mentor_note"])

        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Bottom navigation bar
# ══════════════════════════════════════════════════════════════════════════════
def _render_nav():
    st.markdown('<div class="nav-bar-wrap">', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("🏠\nInício", key="nav_home"):
            _nav("welcome")
    with c2:
        if st.button("🧪\nDiagnóst", key="nav_assess"):
            _nav("assessment")
    with c3:
        if st.button("📈\nProgresso", key="nav_prog"):
            _nav("progress")
    with c4:
        if st.button("💬\nChat", key="nav_chat"):
            _nav("chat")
    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════
def main():
    _init_state()
    _inject_css()
    _check_mlx()

    page = st.session_state["page"]
    if page == "welcome":
        page_welcome()
    elif page == "assessment":
        page_assessment()
    elif page == "progress":
        page_progress()
    elif page == "chat":
        page_chat()

    _render_nav()


main()
