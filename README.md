# MagicMentor

AI-powered career mentoring platform that closes the full loop:
**CV → Skill Gap Analysis → Learn with AI → Validate → Match with Jobs**

---

## The Problem

Every existing tool exits after 1-2 steps of the career development loop:
- CV analyzers identify gaps but don't teach
- Learning platforms don't know which jobs you're targeting
- Job scrapers don't know your current skills
- None of them remember you between sessions

## The Solution

MagicMentor is the first platform to close the entire loop, with **persistent memory** so the mentor knows you better over time.

```
┌─────────────────────────────────────────────────────────┐
│                     MAGICMENTOR LOOP                     │
│                                                         │
│  CV Upload  →  Skill Gap  →  Learn (Q&A)  →  Validate  │
│     │              │              │              │       │
│     └──────────────┴──────────────┴──────────────┘       │
│                          │                               │
│                    Job Matching                          │
│              (score improves as you learn)               │
└─────────────────────────────────────────────────────────┘
```

---

## Architecture

### AI Stack

| Component | Model | Role |
|-----------|-------|------|
| **Mentor Agent** | Qwen3-8B (local via MLX) | CV analysis, career advice, roadmap |
| **Learning Agent** | Qwen3-8B (local via MLX) | Socratic Q&A tutor |
| **Matching Agent** | Qwen3-8B (local via MLX) | Job scoring and ranking |
| **Market Research** | Perplexity sonar-pro | Real-time job market trends |
| **Memory Consolidation** | Qwen3-8B (local via MLX) | Background fact extraction (LangMem pattern) |

Runs **100% locally** on Apple Silicon — no API key needed for the core AI (only Perplexity for market data).

### Memory Architecture (Hybrid Tier 1 + Tier 2)

Based on the 2026 consensus from LangMem, Mem0, and MemGPT research:

```
Tier 1: Structured Profile (JSON)        O(1) lookup
  └── Current skills, target role,
      preferences, career goals

Tier 2: Session Memory (JSONL log)       Chronological
  └── Session summaries, mentor notes,
      extracted facts, skill completions

Background Consolidation (async)         Zero latency
  └── After each session, Claude extracts
      new facts and merges into profile
```

**Result**: 26% accuracy improvement, 90%+ token savings vs. naive full-context injection.

### Job Scraping (Free Sources)

| Source | Via |
|--------|-----|
| LinkedIn | python-jobspy |
| Indeed | python-jobspy |
| Glassdoor | python-jobspy |
| ZipRecruiter | python-jobspy |
| Google Jobs | python-jobspy |
| Web search fallback | Perplexity sonar-pro |

---

## Project Structure

```
magicmentor/
├── cli.py                      # Interactive terminal interface
├── .env                        # API keys (gitignored)
├── .env.example                # Template
│
└── backend/
    ├── main.py                 # FastAPI app
    ├── config.py               # Settings (pydantic-settings)
    ├── database.py             # SQLAlchemy + SQLite
    │
    ├── memory/
    │   ├── persistent_memory.py  # Tier 1+2 memory (JSON-based)
    │   └── consolidator.py       # Background memory extraction (LangMem pattern)
    │
    ├── agents/
    │   ├── mentor_agent.py     # Career mentor (Claude)
    │   ├── learning_agent.py   # Socratic tutor (Claude)
    │   └── matching_agent.py   # Job matcher (Claude)
    │
    ├── scrapers/
    │   └── job_scraper.py      # JobSpy + Perplexity fallback
    │
    ├── parsers/
    │   └── cv_parser.py        # PDF/text → structured data (Claude)
    │
    ├── models/                 # SQLAlchemy models
    │   ├── user.py
    │   ├── skill.py
    │   ├── job.py
    │   └── learning.py
    │
    └── api/routes/             # FastAPI routes
        ├── profile.py
        ├── mentor.py
        ├── learning.py
        └── jobs.py
```

---

## Setup

### 1. Install dependencies

```bash
cd /Users/joaovicente/apps/magicmentor
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 2. Start the local AI model (Apple Silicon required)

```bash
# Download the model (first time only, ~5GB)
mlx_lm.convert --hf-path Qwen/Qwen3-8B --mlx-path ~/Desktop/apps/MLX/Qwen3-8B-4bit -q

# Start the server
KMP_DUPLICATE_LIB_OK=TRUE mlx_lm.server --model ~/Desktop/apps/MLX/Qwen3-8B-4bit --port 8080
```

Or just double-click `MagicMentor.command` — it handles everything automatically.

### 3. Configure API keys

```bash
cp .env.example .env
# Edit .env and add your Perplexity API key (optional — market research only)
```

### 4. Run the CLI

```bash
python cli.py
```

### 4. Run the API server

```bash
uvicorn backend.main:app --reload
# Open http://localhost:8000/docs
```

---

## Usage Flow

### Via CLI

```
1. Start: python cli.py
2. Choose: Use demo CV or paste your own
3. Menu:
   1 → Get career analysis (skill gaps + learning roadmap)
   2 → Start learning a skill (Socratic Q&A)
   3 → Find matching jobs (scraped + AI-scored)
   4 → Chat with mentor
   5 → View your memory/progress
```

### Via API

```bash
# Parse your CV
curl -X POST http://localhost:8000/api/v1/profile/parse-text \
  -H "Content-Type: application/json" \
  -d '{"cv_text": "João Vicente, Python Developer..."}'

# Get mentor analysis
curl -X POST http://localhost:8000/api/v1/mentor/analyze \
  -H "Content-Type: application/json" \
  -d '{"cv_text": "...", "target_role": "Backend Developer", "fetch_market_data": true}'

# Start learning session
curl -X POST http://localhost:8000/api/v1/learning/start \
  -H "Content-Type: application/json" \
  -d '{"skill_name": "FastAPI", "user_level": "beginner"}'

# Find matching jobs
curl -X POST http://localhost:8000/api/v1/jobs/match \
  -H "Content-Type: application/json" \
  -d '{"search_term": "Backend Developer", "location": "Portugal", "score_matches": true}'
```

---

## Persistent Memory

After every session, MagicMentor runs a background memory consolidation step:

1. Claude reads the conversation
2. Extracts durable facts ("User wants to move to ML in 12 months")
3. Merges into the user's profile JSON
4. Saves a session summary

At the start of the next session, the mentor loads this context — so it remembers:
- Your current skills and what you've validated
- Your career goals and concerns
- Your learning style and preferences
- What you discussed last time

Memory is stored in `data/users/{user_id}/memory.json` — fully readable, editable by you.

---

## Differentiators vs Existing Tools

| Feature | MagicMentor | SKANA | Resume-Matcher | Jobright.ai |
|---------|-------------|-------|----------------|-------------|
| CV → Skill Gap | ✓ | ✓ | ✓ | ✓ |
| Multi-source Job Scraping | ✓ | ✗ | ✗ | ✓ |
| AI Learning (Q&A) | ✓ | ✗ | ✗ | ✗ |
| Skill Validation | ✓ | ✗ | ✗ | ✗ |
| Dynamic Re-matching | ✓ | ✗ | ✗ | ✗ |
| Persistent Memory | ✓ | ✗ | ✗ | ✗ |
| Real-time Market Data | ✓ (Perplexity) | ✗ | ✗ | Partial |
| Open Source | ✓ | ✓ | ✓ | ✗ |

---

## Roadmap

- [ ] Frontend (Next.js)
- [ ] Vector DB (Chroma/FAISS) for episodic memory Tier 2
- [ ] Skill graph (interconnected skill relationships)
- [ ] Interview preparation mode
- [ ] LinkedIn import
- [ ] Email digest with new matching jobs
- [ ] Multi-user support with auth
