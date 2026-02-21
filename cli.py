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
from backend.agents.cv_updater import generate_cv_updates


# ── Colours ─────────────────────────────────────────────────────────────────

R  = "\033[0m"       # reset
B  = "\033[1m"       # bold
DM = "\033[2m"       # dim
CY = "\033[96m"      # bright cyan
GR = "\033[92m"      # bright green
YL = "\033[93m"      # bright yellow
RD = "\033[91m"      # bright red
BL = "\033[94m"      # bright blue
MG = "\033[95m"      # bright magenta
WH = "\033[97m"      # bright white

def c(text, colour):   return f"{colour}{text}{R}"
def bold(text):        return f"{B}{text}{R}"
def dim(text):         return f"{DM}{text}{R}"
def bar(val, width=12):
    filled = max(0, min(width, int(val / 100 * width)))
    return c("█" * filled, GR) + c("░" * (width - filled), DM)


# ── UI helpers ───────────────────────────────────────────────────────────────

def clr():
    os.system("clear" if os.name != "nt" else "cls")

def header():
    w = 60
    print()
    print(c("╔" + "═" * (w - 2) + "╗", CY))
    title = "MagicMentor  —  AI Career Mentor"
    pad   = (w - 2 - len(title)) // 2
    print(c("║" + " " * pad + bold(title) + " " * (w - 2 - pad - len(title)) + "║", CY))
    print(c("╚" + "═" * (w - 2) + "╝", CY))

def section(title: str):
    print(f"\n  {c('━' * 50, DM)}")
    print(f"  {bold(c(title, CY))}")
    print(f"  {c('━' * 50, DM)}")

def divider(label: str = ""):
    if label:
        print(f"\n  {c('─── ' + label + ' ', YL)}{c('─' * max(0, 44 - len(label)), DM)}")
    else:
        print(f"  {c('─' * 50, DM)}")

def ok(text):   print(f"  {c('✓', GR)}  {text}")
def warn(text): print(f"  {c('!', YL)}  {text}")
def err(text):  print(f"  {c('✗', RD)}  {text}")
def info(text): print(f"  {dim(text)}")

def ask(prompt: str, default: str = "") -> str:
    arrow = c("›", CY)
    if default:
        hint  = dim(f"[{default}]")
        val   = input(f"\n  {arrow} {bold(prompt)} {hint} ").strip()
        return val or default
    return input(f"\n  {arrow} {bold(prompt)}: ").strip()

def print_json(data: dict, indent: int = 2):
    print(json.dumps(data, indent=indent, ensure_ascii=False, default=str))


# ── CV input ─────────────────────────────────────────────────────────────────

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
    divider("CV")
    print(f"  {dim('Como queres fornecer o teu CV?')}")
    print(f"  {c('1', WH)}  Colar texto")
    print(f"  {c('2', WH)}  Caminho para PDF ou ficheiro de texto")
    if pdf_hint:
        print(f"  {c('3', WH)}  Usar {bold(pdf_hint.name)} {c('(detectado)', GR)}")
    else:
        print(f"  {c('3', WH)}  Usar CV demo (João Vicente)")
    choice = ask("Escolha", "3")

    if choice == "1":
        print(f"\n  {dim('Cola o teu CV abaixo. Linha vazia para terminar:')}")
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
        path = ask("Caminho do ficheiro")
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


# ── Flows ────────────────────────────────────────────────────────────────────

def flow_mentor(cv_text: str, mem) -> dict:
    section("ANÁLISE DO MENTOR")
    target_role = ask("Cargo alvo", "Backend Developer")

    print(f"\n  {c('⟳', CY)} A pesquisar dados de mercado no Perplexity...", end=" ", flush=True)
    market = get_market_insights(target_role, [s.get("name") for s in mem.skills.get("current", [])])
    if "market_demand" in market:
        print(c("pronto", GR))
    else:
        print(dim("ignorado (sem API key)"))

    print(f"  {c('⟳', CY)} A analisar o teu perfil... {dim('(pode demorar 20-30s)')}", flush=True)
    result = analyze_profile(cv_text, market_insights=market, user_memory=mem)

    if "error" in result:
        err(f"Erro: {result}")
        return {}

    # ── Career summary ──────────────────────────────────────────────────
    divider("RESUMO DE CARREIRA")
    print(f"\n  {result.get('career_summary', '')}\n")

    strengths = result.get("key_strengths", [])
    if strengths:
        print("  " + "  ".join(c(f"+ {s}", GR) for s in strengths[:4]))

    # ── Skill gaps ──────────────────────────────────────────────────────
    divider("LACUNAS A FECHAR")
    for gap in result.get("skill_gaps", [])[:5]:
        hot    = gap.get("job_market_demand") == "high"
        tag    = f"  {c('PROCURADO', YL)}" if hot else ""
        time_s = dim(gap.get("estimated_learning_time", "?"))
        num    = c(f"#{gap.get('priority', '?')}", MG)
        print(f"\n  {num}  {bold(gap['skill'])}{tag}  {time_s}")
        print(f"      {dim(gap.get('reason', ''))}")
        print(f"      {dim('Baseia-se em:')} {gap.get('builds_on', 'N/A')}")
        resources = gap.get("resources", [])
        for r in (resources[:2] if resources else []):
            if isinstance(r, dict):
                free_tag = c("[FREE]", GR) if r.get("free") else c("[PAGO]", YL)
                print(f"      {free_tag} {r.get('name', '')}  {c(r.get('url', ''), BL)}")

    # ── Recommended roles ───────────────────────────────────────────────
    divider("ROLES RECOMENDADAS")
    for role in result.get("recommended_roles", [])[:3]:
        pct     = role.get("match_percentage", 0)
        salary  = dim(role.get("avg_salary", ""))
        timeline = dim(role.get("realistic_timeline", ""))
        print(f"\n  {bold(role['title'])}")
        print(f"     {bar(pct)}  {c(str(pct) + '%', GR)}   {salary}   {timeline}")

    # ── Roadmap ─────────────────────────────────────────────────────────
    divider("ROADMAP — próximas 4 semanas")
    for week in result.get("learning_roadmap", [])[:4]:
        wnum = c(f"Semana {week.get('week', '?')}", CY)
        hrs  = dim(f"{week.get('daily_hours', 2)}h/dia")
        print(f"  {wnum}  {week.get('focus', '')}  {hrs}")

    # ── Next action ─────────────────────────────────────────────────────
    next_action = result.get("next_action", "")
    if next_action:
        print()
        print(f"  {c('PRÓXIMA ACÇÃO', YL)}  {bold(next_action)}")

    return result


# ── Learning helpers ─────────────────────────────────────────────────────────

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
    section("SESSÃO DE APRENDIZAGEM")

    # Load from persistent memory if no fresh analysis
    if not analysis or not analysis.get("skill_gaps"):
        saved = mem.get_last_analysis()
        if saved and saved.get("skill_gaps"):
            info("(a usar skill gaps da tua última sessão com o mentor)")
            analysis = saved

    # ── Build options list ──────────────────────────────────────────────
    options = []

    # 1. In-progress sessions (resume)
    active = mem.list_active_sessions()
    if active:
        divider("Em progresso")
        for s in active:
            paused    = s.get("paused_at", "")[:10]
            exchanges = s.get("message_count", 0)
            idx       = len(options) + 1
            print(f"  {c(str(idx), WH)}  {c('↩', YL)}  Continuar {bold(s['skill'])}  {dim(f'{exchanges} trocas · pausado {paused}')}")
            options.append({"skill": s["skill"], "gap_info": None, "resume": True, "level": s.get("level", "beginner")})

    # 2. Mentor analysis gaps
    gaps = analysis.get("skill_gaps", []) if analysis else []
    if gaps:
        divider("Do teu plano com o mentor")
        for gap in gaps[:5]:
            hot      = gap.get("job_market_demand") == "high"
            tag      = f"  {c('PROCURADO', YL)}" if hot else ""
            time_est = dim(gap.get("estimated_learning_time", ""))
            idx      = len(options) + 1
            print(f"  {c(str(idx), WH)}  {bold(gap['skill'])}{tag}  {time_est}")
            options.append({"skill": gap["skill"], "gap_info": gap, "resume": False, "level": "beginner"})

    # 3. Mentor chat skills
    chat_skills = mem.get_mentor_chat_skills()
    if chat_skills:
        divider("Decidido nas conversas com o mentor")
        for cs in chat_skills:
            if any(o["skill"].lower() == cs["skill"].lower() for o in options):
                continue
            idx = len(options) + 1
            print(f"  {c(str(idx), WH)}  {bold(cs['skill'])}")
            options.append({"skill": cs["skill"], "gap_info": None, "resume": False, "level": "beginner"})

    print()
    if not options:
        raw = ask("Que skill queres aprender?")
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
                err("Número inválido.")
                return
        except ValueError:
            options.append({"skill": raw, "gap_info": None, "resume": False, "level": "beginner"})
            choice_idx = len(options) - 1

    chosen   = options[choice_idx]
    skill    = chosen["skill"]
    gap_info = chosen.get("gap_info")
    resuming = chosen.get("resume", False)

    # ── Start or resume ─────────────────────────────────────────────────
    if resuming:
        saved_session = mem.load_learning_session(skill)
        history       = saved_session["history"]
        level         = saved_session.get("level", "beginner")
        divider(f"A retomar · {skill}")
        info(f"{saved_session.get('message_count', 0)} trocas anteriores carregadas")
    else:
        level          = ask("Nível actual (beginner / intermediate / advanced)", chosen.get("level", "beginner"))
        mentor_context = _build_mentor_context(skill, gap_info, analysis)
        session        = start_learning_session(skill, level, user_memory=mem, context=mentor_context)
        history        = session["history"]
        divider(f"Tutor · {skill}")
        print(f"\n  {session['message']}\n")

    print(f"  {dim('Comandos:')}  {c('validate', CY)} — quiz final   {c('back', CY)} — pausar e sair\n")
    print(f"  {c('─' * 50, DM)}\n")

    # ── Conversation loop ───────────────────────────────────────────────
    while True:
        try:
            user_input = ask("Tu").strip()
        except (KeyboardInterrupt, EOFError):
            mem.save_learning_session(skill, level, history)
            print(f"\n  {c('Sessão pausada.', YL)} Progresso guardado.")
            break
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q", "back"):
            mem.save_learning_session(skill, level, history)
            ok("Sessão pausada. Progresso guardado.")
            break
        if user_input.lower() == "validate":
            print(f"\n  {c('⟳', CY)} A correr quiz de validação final...\n")
            result = run_final_validation(skill, history, user_memory=mem)
            print(f"  {result['message']}")
            if result.get("final_score"):
                score = result["final_score"]
                color = GR if score >= 70 else YL
                print(f"\n  {dim('─' * 40)}")
                print(f"  Pontuação final:  {c(bold(f'{score}/100'), color)}  {bar(score)}")
                ready = result.get("ready_for_cv")
                print(f"  Pronto para CV:   {c('SIM!', GR) if ready else c('Ainda não', YL)}")
                mem.delete_learning_session(skill)
            break

        result  = continue_learning(user_input, history, skill, user_memory=mem)
        history = result["history"]
        print(f"\n  {c('Tutor', MG)}  {result['message']}\n")

        if result.get("quiz_score"):
            score = result["quiz_score"]
            print(f"  {dim('Pontuação parcial:')} {c(bold(f'{score}/100'), GR)}  {bar(score)}\n")

        if result.get("session_complete"):
            ok("Parabéns! Completaste esta sessão de aprendizagem!")
            mem.delete_learning_session(skill)
            break


def flow_jobs(mem, analysis: dict = None):
    section("MATCHING DE EMPREGOS")

    default_role = "Software Developer"
    if analysis and analysis.get("recommended_roles"):
        default_role = analysis["recommended_roles"][0]["title"]
    elif mem.profile.get("target_role"):
        default_role = mem.profile["target_role"]

    search   = ask("Pesquisar por", default_role)
    location = ask("Localização", settings.DEFAULT_LOCATION)
    score    = ask("Pontuar matches com IA? (mais lento) [y/n]", "y").lower() == "y"

    print(f"\n  {c('⟳', CY)} A pesquisar empregos para {bold(search)} em {bold(location)}...", flush=True)
    jobs = scrape_jobs(search_term=search, location=location, results_wanted=20)

    if not jobs:
        warn("Nenhum emprego encontrado. Tenta termos diferentes.")
        return

    print(f"  {c(str(len(jobs)), WH)} empregos encontrados.", end=" ")

    if score:
        print(f"\n  {c('⟳', CY)} A pontuar matches com IA {dim('(pode demorar 1-2 min)')}...", flush=True)
        user_profile = {
            "skills": mem.skills.get("current", []),
            "completed_skills": mem.skills.get("completed", []),
            **mem.profile,
        }
        jobs = rank_jobs(user_profile, jobs, max_jobs=10)

    divider("TOP EMPREGOS")
    for i, job in enumerate(jobs[:5], 1):
        score_val = job.get("match_score", None)
        potential = job.get("potential_match_score")
        remote    = c("Remoto", GR) if job.get("is_remote") else dim("Presencial")
        salary    = ""
        if job.get("salary_min") and job.get("salary_max"):
            s_min  = f"{job['salary_min']:.0f}"
            s_max  = f"{job['salary_max']:.0f}"
            salary = f"  {c(s_min + '–' + s_max + 'k', YL)}"

        print(f"\n  {c(f'#{i}', MG)}  {bold(job['title'])}  {dim('@')}  {c(job['company'], WH)}")
        print(f"      {dim(job['location'])}  ·  {remote}{salary}")

        if isinstance(score_val, (int, float)):
            pot_str = f"  {dim('→')}  {c(str(potential) + '%', GR)} após upskilling" if potential else ""
            print(f"      Match  {bar(score_val)}  {c(bold(str(score_val) + '%'), GR)}{pot_str}")
            rec = job.get("recommendation", "")
            if rec:
                print(f"      {dim(rec)}")
        if job.get("quick_wins"):
            print(f"      {c('→', GR)} {job['quick_wins'][0]}")
        if job.get("url"):
            print(f"      {c(job['url'], BL)}")


def flow_chat(mem, cv_text: str = ""):
    section("CHAT COM O MENTOR")
    print(f"  {dim('Fala com o teu mentor de carreira.')}")
    print(f"  {dim('Comandos:')}  {c('memory', CY)} — o que o mentor recorda   {c('back', CY)} — voltar ao menu\n")
    print(f"  {c('─' * 50, DM)}\n")

    history = []
    while True:
        try:
            user_input = ask("Tu").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n  {dim('A voltar ao menu...')}")
            break
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q", "back"):
            break
        if user_input.lower() == "memory":
            print(f"\n{mem.build_context_prompt()}\n")
            continue

        result  = chat_with_mentor(user_input, history, user_memory=mem, profile_context=cv_text[:500])
        history = result["history"]
        print(f"\n  {c('Mentor', MG)}  {result['response']}\n")
        print(f"  {c('─' * 50, DM)}\n")

    # On exit: offer to save any skills/path decided in this conversation
    if history:
        print()
        add = ask("Decidiste um learning path nesta conversa? Adicionar skills? [y/n]", "n").lower()
        if add == "y":
            print(f"  {dim('Indica as skills (linha vazia para terminar):')}")
            while True:
                skill = input(f"  {c('›', CY)} Skill: ").strip()
                if not skill:
                    break
                mem.add_mentor_chat_skill(skill)
                ok(f"'{skill}' adicionado")


def flow_progress(mem):
    section("O TEU PROGRESSO")

    # ── Skills ──────────────────────────────────────────────────────────
    skills = mem.skills

    if skills.get("current"):
        divider("Skills actuais")
        top = [s["name"] for s in skills["current"][:6]]
        for chunk in [top[i:i+3] for i in range(0, len(top), 3)]:
            print("  " + "   ".join(c(s, WH) for s in chunk))

    active_sessions = mem.list_active_sessions()
    if active_sessions:
        divider("Em aprendizagem")
        for s in active_sessions:
            msgs = s.get('message_count', 0)
            print(f"  {c('→', YL)}  {bold(s['skill'])}  {dim(str(msgs) + ' trocas')}")

    if skills.get("completed"):
        divider("Skills validadas")
        for s in skills["completed"]:
            score = s.get("score", 0)
            print(f"  {c('✓', GR)}  {bold(s['name'])}  {c(str(score) + '/100', GR)}  {bar(score, width=8)}")

    # ── Courses ─────────────────────────────────────────────────────────
    all_courses = mem.get_courses()
    pending     = [c_ for c_ in all_courses if not c_["completed"]]
    done        = [c_ for c_ in all_courses if c_["completed"]]

    if not all_courses:
        divider("Cursos")
        info("Sem cursos guardados. Faz a análise do perfil (opção 1) para o mentor sugerir cursos.")
    else:
        if pending:
            divider(f"Cursos para fazer  ({len(pending)})")
            for i, course in enumerate(pending, 1):
                free_tag = c("[FREE]", GR) if course.get("free") else c("[PAGO]", YL)
                print(f"\n  {c(str(i), WH)}  {free_tag}  {bold(course['name'])}")
                print(f"      {dim('Skill:')} {course['skill']}")
                print(f"      {c(course['url'], BL)}")

        if done:
            divider(f"Cursos concluídos  ({len(done)})")
            for course in done:
                date = course.get("completed_at", "")[:10]
                print(f"  {c('✓', GR)}  {course['name']}  {dim(date)}")

        if pending:
            print()
            mark = ask("Marcar curso como concluído? (número ou 'n')", "n")
            if mark.lower() != "n":
                try:
                    idx = int(mark) - 1
                    if mem.mark_course_done(idx):
                        ok(f"'{pending[idx]['name']}' marcado como concluído!")
                    else:
                        err("Número inválido.")
                except ValueError:
                    err("Número inválido.")

    # ── Mentor notes ─────────────────────────────────────────────────────
    notes = mem.data.get("mentor_notes", [])[-2:]
    if notes:
        divider("Notas do mentor")
        for n in notes:
            print(f"  {dim(n['date'][:10])}  {n['note'][:120]}")


def flow_cv_update(mem, cv_text: str):
    section("ACTUALIZAR CV")

    if not cv_text:
        warn("Nenhum CV carregado nesta sessão. Volta ao menu e carrega o teu CV primeiro.")
        return

    # Show what we have to work with
    completed_skills  = mem.skills.get("completed", [])
    in_progress       = mem.skills.get("learning", [])
    completed_courses = [c for c in mem.get_courses() if c.get("completed")]

    if not completed_skills and not in_progress and not completed_courses:
        warn("Ainda não tens progresso registado para adicionar ao CV.")
        info("Completa sessões de aprendizagem (opção 2) ou valida skills para começar.")
        return

    divider("Progresso detectado")
    if completed_skills:
        print(f"  {c('Skills validadas:', GR)}  " + ", ".join(s["name"] for s in completed_skills))
    if completed_courses:
        print(f"  {c('Cursos concluídos:', GR)}  " + ", ".join(c["name"] for c in completed_courses))
    if in_progress:
        print(f"  {c('Em estudo:', YL)}  " + ", ".join(s["name"] for s in in_progress))

    print()
    go = ask("Gerar sugestões de actualização para o CV? [y/n]", "y").lower()
    if go != "y":
        return

    print(f"\n  {c('⟳', CY)} A gerar sugestões com IA...", flush=True)
    result = generate_cv_updates(cv_text, mem)

    if result.get("nothing_yet"):
        warn("Ainda não há progresso suficiente para sugerir actualizações.")
        return

    if result.get("raw"):
        # Fallback: LLM didn't return valid JSON
        divider("Sugestões (texto livre)")
        print(f"\n{result['raw']}")
        return

    # ── Display structured suggestions ─────────────────────────────────
    if result.get("updated_summary"):
        divider("Resumo profissional — sugestão")
        print(f"\n  {result['updated_summary']}\n")

    if result.get("new_skills"):
        divider("Skills a adicionar")
        for bullet in result["new_skills"]:
            print(f"  {c('▸', GR)}  {bullet}")

    if result.get("new_courses"):
        divider("Cursos / Certificações a adicionar")
        for bullet in result["new_courses"]:
            print(f"  {c('▸', GR)}  {bullet}")

    if result.get("in_progress"):
        divider("Em progresso (opcional incluir no CV)")
        for bullet in result["in_progress"]:
            print(f"  {c('▸', YL)}  {bullet}")

    if result.get("full_skills_block"):
        divider("Secção SKILLS actualizada — pronta a colar")
        print()
        for line in result["full_skills_block"].splitlines():
            print(f"  {line}")

    # ── Save to file ────────────────────────────────────────────────────
    from datetime import datetime
    date_str  = datetime.now().strftime("%Y-%m-%d")
    user_dir  = Path(settings.MEMORY_DIR) / str(mem.user_id)
    out_path  = user_dir / f"CV_update_{date_str}.md"

    md_lines = [f"# CV Update Suggestions — {date_str}\n"]
    if result.get("updated_summary"):
        md_lines += ["## Resumo profissional\n", result["updated_summary"], ""]
    if result.get("new_skills"):
        md_lines += ["## Skills a adicionar\n"] + [f"- {b}" for b in result["new_skills"]] + [""]
    if result.get("new_courses"):
        md_lines += ["## Cursos / Certificações\n"] + [f"- {b}" for b in result["new_courses"]] + [""]
    if result.get("in_progress"):
        md_lines += ["## Em progresso\n"] + [f"- {b}" for b in result["in_progress"]] + [""]
    if result.get("full_skills_block"):
        md_lines += ["## Secção SKILLS completa\n", "```", result["full_skills_block"], "```", ""]

    out_path.write_text("\n".join(md_lines), encoding="utf-8")
    print()
    ok(f"Sugestões guardadas em {c(str(out_path), BL)}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    clr()
    header()

    # Check MLX server is running (local model — no API key needed)
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:8080/v1/models", timeout=3)
    except Exception:
        err("Servidor MLX não está a correr em localhost:8080")
        info("Inicia via: KMP_DUPLICATE_LIB_OK=TRUE mlx_lm.server --model ~/Desktop/apps/MLX/Qwen3-8B-4bit --port 8080")
        sys.exit(1)

    if not settings.PERPLEXITY_API_KEY:
        warn("PERPLEXITY_API_KEY não definida — pesquisa de mercado desactivada.")

    # Auto-detect user folder (e.g. "JV") or fall back to 1
    users_dir    = Path(settings.MEMORY_DIR)
    named_folders = [d.name for d in users_dir.iterdir() if d.is_dir() and not d.name.isdigit()] if users_dir.exists() else []
    user_id      = named_folders[0] if named_folders else 1
    mem          = get_user_memory(user_id)

    print(f"\n  {bold('Bem-vindo ao MagicMentor!')}")
    if isinstance(user_id, str):
        print(f"  {dim('Perfil:')} {c(user_id, CY)}")

    # Auto-detect CV PDF in user folder
    user_dir  = Path(settings.MEMORY_DIR) / str(user_id)
    pdf_files = list(user_dir.glob("*.pdf"))

    if mem.profile.get("name"):
        print(f"  {c('Bem-vindo de volta,', GR)} {bold(mem.profile['name'])}!")
        use_saved = ask("Usar perfil guardado? [y/n]", "y").lower() == "y"
        cv_text   = "" if use_saved else get_cv(pdf_hint=pdf_files[0] if pdf_files else None)
    elif pdf_files:
        print(f"\n  {c('CV encontrado:', GR)} {bold(pdf_files[0].name)}")
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
        section("MENU PRINCIPAL")
        print(f"  {c('1', WH)}  Analisar perfil & obter plano de carreira")
        print(f"  {c('2', WH)}  Sessão de aprendizagem")
        print(f"  {c('3', WH)}  Encontrar empregos")
        print(f"  {c('4', WH)}  Chat com o mentor")
        print(f"  {c('5', WH)}  O teu progresso")
        print(f"  {c('6', WH)}  Actualizar CV com o meu progresso")
        print(f"  {c('0', DM)}  Sair")

        choice = ask("Escolha")

        if choice == "1":
            if not cv_text:
                cv_text = get_cv(pdf_hint=pdf_files[0] if pdf_files else None)
            analysis = flow_mentor(cv_text, mem)

        elif choice == "2":
            flow_learning(mem, analysis)

        elif choice == "3":
            flow_jobs(mem, analysis)

        elif choice == "4":
            flow_chat(mem, cv_text)

        elif choice == "5":
            flow_progress(mem)

        elif choice == "6":
            flow_cv_update(mem, cv_text)

        elif choice == "0":
            print(f"\n  {c('Até já! Continua a aprender.', GR)}\n")
            break


if __name__ == "__main__":
    main()
