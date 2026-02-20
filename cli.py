#!/usr/bin/env python3
"""
MagicMentor CLI
===============
Interactive terminal interface for MagicMentor.
Lets you test all features without running the web server.

Usage:
    python cli.py
"""

import os
import sys
import json
from pathlib import Path

# Ensure we can import backend
sys.path.insert(0, str(Path(__file__).parent))

# Load .env
from dotenv import load_dotenv
load_dotenv()

from backend.config import settings
from backend.parsers.cv_parser import parse_cv
from backend.agents.mentor_agent import analyze_profile, chat_with_mentor
from backend.agents.learning_agent import start_learning_session, continue_learning, run_final_validation
from backend.agents.matching_agent import rank_jobs
from backend.scrapers.job_scraper import scrape_jobs, get_market_insights
from backend.memory.persistent_memory import get_user_memory


# ── UI helpers ──────────────────────────────────────────────────────────────

def clr():
    os.system("clear" if os.name != "nt" else "cls")

def header():
    print("\n" + "="*60)
    print("        MagicMentor  — AI Career Mentor")
    print("="*60)

def section(title: str):
    print(f"\n{'─'*55}")
    print(f"  {title}")
    print("─"*55)

def ask(prompt: str, default: str = "") -> str:
    if default:
        val = input(f"{prompt} [{default}]: ").strip()
        return val or default
    return input(f"{prompt}: ").strip()

def print_json(data: dict, indent: int = 2):
    print(json.dumps(data, indent=indent, ensure_ascii=False, default=str))


# ── CV input ────────────────────────────────────────────────────────────────

DEMO_CV = """
João Vicente
Software Developer | Porto, Portugal
joao@email.com | +351 912 345 678

EXPERIENCE
----------
Junior Python Developer — WebCompany (2022–2024, 2 years)
  Technologies: Python, Django, HTML, CSS, JavaScript, PostgreSQL, Git, REST APIs
  - Built internal CRM reducing manual work by 30%
  - Maintained and extended legacy Django monolith

IT Support Technician — LocalBusiness (2021–2022, 1 year)
  Technologies: Windows Server, basic networking, Active Directory

EDUCATION
---------
BSc Computer Science — University of Porto (2021)

SKILLS
------
Python (intermediate, 2 years) | Django (intermediate, 2 years)
JavaScript (basic, 1 year) | PostgreSQL (basic, 1 year)
Git (intermediate, 2 years) | HTML/CSS (intermediate, 2 years)
Linux (basic) | REST APIs (intermediate)

LANGUAGES: Portuguese (native), English (B2)
"""


def get_cv(pdf_hint: Path = None) -> str:
    print("\nHow do you want to provide your CV?")
    print("  1  Paste CV text")
    print("  2  Path to PDF or text file")
    if pdf_hint:
        print(f"  3  Use {pdf_hint.name} (detected)")
    else:
        print("  3  Use demo CV (João Vicente)")
    choice = ask("Choice", "3")

    if choice == "1":
        print("\nPaste your CV below. Press Enter twice to finish:")
        lines, blank = [], 0
        while blank < 1:
            line = input()
            if line == "":
                blank += 1
            else:
                blank = 0
                lines.append(line)
        return "\n".join(lines)

    elif choice == "2":
        path = ask("File path")
        if path.lower().endswith(".pdf"):
            from backend.parsers.cv_parser import extract_text_from_pdf
            return extract_text_from_pdf(path)
        else:
            with open(path, encoding="utf-8") as f:
                return f.read()

    # choice == "3"
    if pdf_hint:
        from backend.parsers.cv_parser import extract_text_from_pdf
        return extract_text_from_pdf(str(pdf_hint))
    return DEMO_CV


# ── Flows ───────────────────────────────────────────────────────────────────

def flow_mentor(cv_text: str, mem) -> dict:
    section("MENTOR ANALYSIS")
    target_role = ask("Target role (optional)", "Backend Developer")

    print("\nFetching market data from Perplexity...", end=" ", flush=True)
    market = get_market_insights(target_role, [s.get("name") for s in mem.skills.get("current", [])])
    print("done" if "market_demand" in market else "skipped (no API key)")

    print("Analyzing your profile with Claude... (this may take 20-30s)")
    result = analyze_profile(cv_text, market_insights=market, user_memory=mem)

    if "error" in result:
        print(f"\nError: {result}")
        return {}

    print(f"\n{'='*55}")
    print(f"  CAREER SUMMARY")
    print(f"{'='*55}")
    print(result.get("career_summary", ""))

    strengths = result.get("key_strengths", [])
    if strengths:
        print(f"\n  Strengths: {' | '.join(strengths[:4])}")

    print(f"\n  TOP SKILL GAPS TO CLOSE:")
    for gap in result.get("skill_gaps", [])[:5]:
        demand = "HOT" if gap.get("job_market_demand") == "high" else "   "
        print(f"  [{demand}] #{gap.get('priority', '?')} {gap['skill']}")
        print(f"        {gap.get('reason', '')}")
        print(f"        Time: {gap.get('estimated_learning_time', '?')} | Builds on: {gap.get('builds_on', 'N/A')}")

    print(f"\n  RECOMMENDED ROLES:")
    for role in result.get("recommended_roles", [])[:3]:
        print(f"  • {role['title']} — {role.get('match_percentage', '?')}% match | {role.get('avg_salary', '')} | {role.get('realistic_timeline', '')}")

    print(f"\n  LEARNING ROADMAP (next 4 weeks):")
    for week in result.get("learning_roadmap", [])[:4]:
        print(f"  Week {week.get('week', '?')}: {week.get('focus', '')} ({week.get('daily_hours', 2)}h/day)")

    next_action = result.get("next_action", "")
    if next_action:
        print(f"\n  NEXT ACTION: {next_action}")

    return result


def _build_mentor_context(skill: str, gap_info: dict, analysis: dict) -> str:
    """Build context string from mentor analysis for a specific skill."""
    if not gap_info:
        return ""
    ctx = f"Mentor analysis for {skill}:\n"
    ctx += f"- Why it matters: {gap_info.get('reason', '')}\n"
    ctx += f"- Builds on: {gap_info.get('builds_on', 'N/A')}\n"
    ctx += f"- Estimated time: {gap_info.get('estimated_learning_time', '?')}\n"
    if gap_info.get("resources"):
        ctx += f"- Recommended resources: {', '.join(gap_info['resources'])}\n"
    if gap_info.get("job_market_demand") == "high":
        ctx += "- Market demand: HIGH\n"
    if analysis and analysis.get("learning_roadmap"):
        for week in analysis["learning_roadmap"]:
            if skill.lower() in week.get("focus", "").lower():
                ctx += f"\nRoadmap: Week {week['week']} — {week.get('focus', '')}"
                if week.get("milestones"):
                    ctx += f"\nMilestones: {', '.join(week['milestones'])}"
                break
    return ctx


def flow_learning(mem, analysis: dict = None):
    section("LEARNING SESSION")

    # Load from persistent memory if no fresh analysis
    if not analysis or not analysis.get("skill_gaps"):
        saved = mem.get_last_analysis()
        if saved and saved.get("skill_gaps"):
            analysis = saved

    # ── Build options list ──────────────────────────────────────────────
    options = []  # Each: {"label": str, "skill": str, "gap_info": dict|None, "resume": bool, "level": str}

    # 1. In-progress sessions (resume)
    active = mem.list_active_sessions()
    if active:
        print("\n  Em progresso:")
        for s in active:
            paused = s.get("paused_at", "")[:10]
            exchanges = s.get("message_count", 0)
            label = f"  r{len(options)+1}  Continuar '{s['skill']}' ({exchanges} trocas, pausado {paused})"
            print(label)
            options.append({"skill": s["skill"], "gap_info": None, "resume": True, "level": s.get("level", "beginner")})

    # 2. Mentor analysis gaps
    gaps = analysis.get("skill_gaps", []) if analysis else []
    if gaps:
        print("\n  Do teu plano com o mentor:")
        for gap in gaps[:5]:
            demand = " [HOT]" if gap.get("job_market_demand") == "high" else ""
            time_est = gap.get("estimated_learning_time", "")
            time_str = f" ({time_est})" if time_est else ""
            idx = len(options) + 1
            print(f"  {idx}.  {gap['skill']}{time_str}{demand}")
            options.append({"skill": gap["skill"], "gap_info": gap, "resume": False, "level": "beginner"})

    # 3. Mentor chat skills
    chat_skills = mem.get_mentor_chat_skills()
    if chat_skills:
        print("\n  Decidido nas conversas com o mentor:")
        for cs in chat_skills:
            # Skip if already in gaps list
            if any(o["skill"].lower() == cs["skill"].lower() for o in options):
                continue
            idx = len(options) + 1
            print(f"  {idx}.  {cs['skill']}")
            options.append({"skill": cs["skill"], "gap_info": None, "resume": False, "level": "beginner"})

    print()
    if not options:
        raw = ask("What skill do you want to learn?")
        if not raw:
            return
        options.append({"skill": raw, "gap_info": None, "resume": False, "level": "beginner"})
        choice_idx = 0
    else:
        raw = ask("Escolhe (número) ou escreve um skill novo")
        if not raw:
            return
        try:
            choice_idx = int(raw) - 1
            if choice_idx < 0 or choice_idx >= len(options):
                print("Número inválido.")
                return
        except ValueError:
            # New skill typed manually
            options.append({"skill": raw, "gap_info": None, "resume": False, "level": "beginner"})
            choice_idx = len(options) - 1

    chosen = options[choice_idx]
    skill = chosen["skill"]
    gap_info = chosen.get("gap_info")
    resuming = chosen.get("resume", False)

    # ── Start or resume session ─────────────────────────────────────────
    if resuming:
        saved_session = mem.load_learning_session(skill)
        history = saved_session["history"]
        level = saved_session.get("level", "beginner")
        print(f"\n{'='*55}")
        print(f"  A retomar '{skill}' — {saved_session.get('message_count', 0)} trocas anteriores")
        print(f"{'='*55}")
        print("\nComandos: 'validate' — quiz final | 'back' — pausar e sair\n")
    else:
        level = ask("Nível actual (beginner/intermediate/advanced)", chosen.get("level", "beginner"))
        mentor_context = _build_mentor_context(skill, gap_info, analysis)
        session = start_learning_session(skill, level, user_memory=mem, context=mentor_context)
        history = session["history"]
        print(f"\n{'='*55}")
        print(f"  Tutor: {session['message']}")
        print(f"{'='*55}")
        print("\nComandos: 'validate' — quiz final | 'back' — pausar e sair\n")

    # ── Conversation loop ───────────────────────────────────────────────
    while True:
        try:
            user_input = ask("Tu").strip()
        except (KeyboardInterrupt, EOFError):
            mem.save_learning_session(skill, level, history)
            print("\n\nSessão pausada. Progresso guardado!")
            break
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q", "back"):
            mem.save_learning_session(skill, level, history)
            print("\nSessão pausada. Progresso guardado!")
            break
        if user_input.lower() == "validate":
            print("\nA correr quiz de validação final...")
            result = run_final_validation(skill, history, user_memory=mem)
            print(f"\nTutor: {result['message']}")
            if result.get("final_score"):
                print(f"\n{'='*40}")
                print(f"Pontuação final: {result['final_score']}/100")
                print(f"Pronto para CV: {'SIM!' if result.get('ready_for_cv') else 'Ainda não'}")
                mem.delete_learning_session(skill)
            break

        result = continue_learning(user_input, history, skill, user_memory=mem)
        history = result["history"]
        print(f"\nTutor: {result['message']}\n")

        if result.get("quiz_score"):
            print(f"  [Pontuação: {result['quiz_score']}/100]")

        if result.get("session_complete"):
            print("\nParabéns! Completaste esta sessão de aprendizagem!")
            mem.delete_learning_session(skill)
            break


def flow_jobs(mem, analysis: dict = None):
    section("JOB MATCHING")

    default_role = "Software Developer"
    if analysis and analysis.get("recommended_roles"):
        default_role = analysis["recommended_roles"][0]["title"]
    elif mem.profile.get("target_role"):
        default_role = mem.profile["target_role"]

    search = ask("Search for", default_role)
    location = ask("Location", settings.DEFAULT_LOCATION)
    score = ask("Score matches with AI? (slower but detailed) [y/n]", "y").lower() == "y"

    print(f"\nScraping jobs for '{search}' in {location}...")
    jobs = scrape_jobs(search_term=search, location=location, results_wanted=20)

    if not jobs:
        print("No jobs found. Try different terms.")
        return

    print(f"Found {len(jobs)} jobs.", end=" ")

    if score:
        print("Scoring matches with Claude (may take 1-2 min)...")
        user_profile = {
            "skills": mem.skills.get("current", []),
            "completed_skills": mem.skills.get("completed", []),
            **mem.profile,
        }
        jobs = rank_jobs(user_profile, jobs, max_jobs=10)

    print(f"\n{'='*55}")
    print(f"  TOP JOB MATCHES")
    print(f"{'='*55}")

    for i, job in enumerate(jobs[:5], 1):
        score_val = job.get("match_score", "N/A")
        potential = job.get("potential_match_score")
        remote = "Remote" if job.get("is_remote") else "On-site"
        salary = ""
        if job.get("salary_min") and job.get("salary_max"):
            salary = f" | {job['salary_min']:.0f}-{job['salary_max']:.0f}k"

        print(f"\n  #{i} {job['title']} @ {job['company']}")
        print(f"     {job['location']} | {remote}{salary}")
        if isinstance(score_val, (int, float)):
            potential_str = f" → {potential}% after upskilling" if potential else ""
            print(f"     Match: {score_val}%{potential_str}")
            print(f"     {job.get('recommendation', '')}")
        if job.get("quick_wins"):
            print(f"     Quick win: {job['quick_wins'][0]}")
        print(f"     {job.get('url', 'N/A')}")


def flow_chat(mem, cv_text: str = ""):
    section("MENTOR CHAT")
    print("Chat with your AI mentor.")
    print("Commands: 'memory' — what the mentor remembers | 'back' or 'q' — return to menu\n")

    history = []
    while True:
        try:
            user_input = ask("You").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nReturning to menu...")
            break
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q", "back"):
            break
        if user_input.lower() == "memory":
            print(f"\n{mem.build_context_prompt()}\n")
            continue

        result = chat_with_mentor(user_input, history, user_memory=mem, profile_context=cv_text[:500])
        history = result["history"]
        print(f"\nMentor: {result['response']}\n")

    # On exit: offer to save any skills/path decided in this conversation
    if history:
        print("\nDecidiste um learning path nesta conversa?")
        add = ask("Adicionar skills à tua lista? [y/n]", "n").lower()
        if add == "y":
            print("Indica as skills (uma por linha, linha vazia para terminar):")
            while True:
                skill = input("  Skill: ").strip()
                if not skill:
                    break
                mem.add_mentor_chat_skill(skill)
                print(f"  ✓ '{skill}' adicionado")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    clr()
    header()

    # Check MLX server is running (local model — no API key needed)
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:8080/v1/models", timeout=3)
    except Exception:
        print("\nERROR: Servidor MLX não está a correr em localhost:8080")
        print("Inicia via: KMP_DUPLICATE_LIB_OK=TRUE mlx_lm.server --model ~/Desktop/apps/MLX/Qwen3-8B-4bit --port 8080")
        sys.exit(1)

    if not settings.PERPLEXITY_API_KEY:
        print("\n⚠  PERPLEXITY_API_KEY não definida — pesquisa de mercado desactivada.")

    # Auto-detect user folder (e.g. "JV") or fall back to 1
    users_dir = Path(settings.MEMORY_DIR)
    named_folders = [d.name for d in users_dir.iterdir() if d.is_dir() and not d.name.isdigit()] if users_dir.exists() else []
    user_id = named_folders[0] if named_folders else 1
    mem = get_user_memory(user_id)

    print(f"\nWelcome to MagicMentor!")
    if isinstance(user_id, str):
        print(f"Profile: {user_id}")

    # Auto-detect CV PDF in user folder
    user_dir = Path(settings.MEMORY_DIR) / str(user_id)
    pdf_files = list(user_dir.glob("*.pdf"))

    if mem.profile.get("name"):
        print(f"Welcome back, {mem.profile['name']}!")
        use_saved = ask("Use saved profile? [y/n]", "y").lower() == "y"
        if use_saved:
            cv_text = ""
        else:
            cv_text = get_cv(pdf_hint=pdf_files[0] if pdf_files else None)
    elif pdf_files:
        print(f"\nCV encontrado: {pdf_files[0].name}")
        use_pdf = ask("Usar este CV? [y/n]", "y").lower() == "y"
        if use_pdf:
            from backend.parsers.cv_parser import extract_text_from_pdf
            cv_text = extract_text_from_pdf(str(pdf_files[0]))
        else:
            cv_text = get_cv()
    else:
        cv_text = get_cv()

    analysis = {}

    while True:
        section("MAIN MENU")
        print("  1  Analyze my profile & get career plan")
        print("  2  Start a learning session")
        print("  3  Find matching jobs")
        print("  4  Chat with mentor")
        print("  5  View my memory/progress")
        print("  0  Exit")

        choice = ask("\nChoice")

        if choice == "1":
            if not cv_text:
                cv_text = get_cv()
            analysis = flow_mentor(cv_text, mem)

        elif choice == "2":
            flow_learning(mem, analysis)

        elif choice == "3":
            flow_jobs(mem, analysis)

        elif choice == "4":
            flow_chat(mem, cv_text)

        elif choice == "5":
            section("YOUR PROGRESS")
            print(mem.build_context_prompt())
            skills = mem.skills
            if skills.get("completed"):
                print("\nValidated skills:")
                for s in skills["completed"]:
                    print(f"  ✓ {s['name']} ({s.get('score', '?')}/100)")

        elif choice == "0":
            print("\nGoodbye! Keep learning! \n")
            break


if __name__ == "__main__":
    main()
