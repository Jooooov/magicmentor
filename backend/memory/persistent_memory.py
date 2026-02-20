"""
Persistent Memory for MagicMentor
===================================
Implements a file-based memory system that keeps context across sessions.

Architecture (hybrid approach):
- JSON files per user: structured facts, CV, preferences, conversation summaries
- Append-only memory log: what the mentor has learned about the user over time
- Session summaries: key takeaways from each conversation (stored after session ends)

This gives Claude persistent "memory" without bloating context windows.
The mentor loads relevant memory snippets at the start of each session.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from ..config import settings


class UserMemory:
    """
    Persistent memory store for a single user.
    Stored as JSON in data/users/{user_id}/memory.json
    """

    def __init__(self, user_id):
        self.user_id = user_id
        self.memory_dir = Path(settings.MEMORY_DIR) / str(user_id)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.memory_file = self.memory_dir / "memory.json"
        self.log_file = self.memory_dir / "memory_log.jsonl"
        self._data = self._load()

    def _load(self) -> dict:
        if self.memory_file.exists():
            with open(self.memory_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return self._default_structure()

    def _default_structure(self) -> dict:
        return {
            "user_id": self.user_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            # Core profile facts (updated when CV is parsed)
            "profile": {
                "name": None,
                "email": None,
                "location": None,
                "years_experience": 0,
                "current_role": None,
                "target_role": None,
            },
            # Skills snapshot (updated after each mentor session)
            "skills": {
                "current": [],       # [{name, level, category}]
                "learning": [],      # Skills in progress
                "completed": [],     # Validated skills
                "targets": [],       # Recommended to learn
            },
            # Mentor notes (updated by mentor after each conversation)
            "mentor_notes": [],       # Chronological list of observations
            # Learning history summary
            "learning_history": [],   # [{skill, date, score, summary}]
            # Last mentor analysis (skill gaps + roadmap) — used by learning session
            "last_mentor_analysis": {
                "skill_gaps": [],
                "learning_roadmap": [],
                "recommended_roles": [],
            },
            # Preferences learned over time
            "preferences": {
                "learning_style": None,     # e.g. "visual", "hands-on"
                "preferred_topics": [],
                "career_goals": [],
                "concerns": [],
            },
            # Session summaries (to avoid loading full transcripts)
            "session_summaries": [],  # [{date, type, summary, key_insights}]
        }

    def save(self):
        self._data["updated_at"] = datetime.utcnow().isoformat()
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def log_event(self, event_type: str, content: str):
        """Append an event to the memory log (immutable audit trail)."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "content": content,
        }
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ── Profile ────────────────────────────────────────────────────────────

    def update_profile(self, profile_data: dict):
        self._data["profile"].update({k: v for k, v in profile_data.items() if v})
        self.log_event("profile_update", json.dumps(profile_data))
        self.save()

    def save_mentor_analysis(self, skill_gaps: list, learning_roadmap: list, recommended_roles: list):
        """Save the full mentor analysis for use across sessions."""
        self._data["last_mentor_analysis"] = {
            "skill_gaps": skill_gaps,
            "learning_roadmap": learning_roadmap,
            "recommended_roles": recommended_roles,
        }
        self.save()

    def get_last_analysis(self) -> dict:
        """Return the last mentor analysis, or empty dict if none."""
        return self._data.get("last_mentor_analysis", {})

    def update_skills(self, current: list = None, targets: list = None):
        if current:
            self._data["skills"]["current"] = current
        if targets:
            self._data["skills"]["targets"] = targets
        self.log_event("skills_update", f"current: {len(current or [])} skills, targets: {len(targets or [])} skills")
        self.save()

    def mark_skill_completed(self, skill_name: str, score: float):
        """Move a skill from 'learning' to 'completed'."""
        self._data["skills"]["learning"] = [
            s for s in self._data["skills"]["learning"]
            if s.get("name") != skill_name
        ]
        self._data["skills"]["completed"].append({
            "name": skill_name,
            "score": score,
            "completed_at": datetime.utcnow().isoformat(),
        })
        self.log_event("skill_completed", f"{skill_name} (score: {score})")
        self.save()

    # ── Mentor notes ───────────────────────────────────────────────────────

    def add_mentor_note(self, note: str):
        """Add a mentor observation about the user."""
        self._data["mentor_notes"].append({
            "date": datetime.utcnow().isoformat(),
            "note": note,
        })
        # Keep only last 20 notes to stay concise
        self._data["mentor_notes"] = self._data["mentor_notes"][-20:]
        self.log_event("mentor_note", note)
        self.save()

    # ── Session summaries ──────────────────────────────────────────────────

    def add_session_summary(self, session_type: str, summary: str, key_insights: list = None):
        """Save a summary after a session ends (avoids loading full transcripts)."""
        self._data["session_summaries"].append({
            "date": datetime.utcnow().isoformat(),
            "type": session_type,       # "mentor_chat", "learning", "job_search"
            "summary": summary,
            "key_insights": key_insights or [],
        })
        # Keep last 10 session summaries
        self._data["session_summaries"] = self._data["session_summaries"][-10:]
        self.save()

    # ── Context builder ────────────────────────────────────────────────────

    def build_context_prompt(self) -> str:
        """
        Build a concise context string to inject into Claude's system prompt.
        This is the 'memory' that the mentor reads at the start of each session.
        """
        d = self._data
        p = d.get("profile", {})

        lines = ["=== USER MEMORY ==="]

        if p.get("name"):
            lines.append(f"Name: {p['name']}")
        if p.get("current_role"):
            lines.append(f"Current role: {p['current_role']}")
        if p.get("target_role"):
            lines.append(f"Target role: {p['target_role']}")
        if p.get("years_experience"):
            lines.append(f"Experience: {p['years_experience']} years")
        if p.get("location"):
            lines.append(f"Location: {p['location']}")

        current_skills = d["skills"].get("current", [])
        if current_skills:
            top_skills = ", ".join(s.get("name", "") for s in current_skills[:8])
            lines.append(f"Current skills: {top_skills}")

        completed = d["skills"].get("completed", [])
        if completed:
            done = ", ".join(s.get("name", "") for s in completed[-5:])
            lines.append(f"Recently validated skills: {done}")

        learning = d["skills"].get("learning", [])
        if learning:
            in_progress = ", ".join(s.get("name", "") for s in learning)
            lines.append(f"Currently learning: {in_progress}")

        recent_notes = d.get("mentor_notes", [])[-3:]
        if recent_notes:
            lines.append("\nMentor notes:")
            for n in recent_notes:
                lines.append(f"  [{n['date'][:10]}] {n['note']}")

        recent_sessions = d.get("session_summaries", [])[-2:]
        if recent_sessions:
            lines.append("\nRecent sessions:")
            for s in recent_sessions:
                lines.append(f"  [{s['date'][:10]}] {s['type']}: {s['summary'][:120]}")

        prefs = d.get("preferences", {})
        if prefs.get("career_goals"):
            lines.append(f"\nCareer goals: {'; '.join(prefs['career_goals'][:3])}")

        lines.append("===================")
        return "\n".join(lines)

    # ── Getters ────────────────────────────────────────────────────────────

    @property
    def profile(self) -> dict:
        return self._data["profile"]

    @property
    def skills(self) -> dict:
        return self._data["skills"]

    @property
    def data(self) -> dict:
        return self._data


def get_user_memory(user_id) -> UserMemory:
    return UserMemory(user_id)
