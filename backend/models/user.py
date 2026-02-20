from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from ..database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    email = Column(String(100), unique=True, index=True)
    cv_text = Column(Text)
    parsed_cv = Column(JSON)          # Structured CV data from Claude
    current_skills = Column(JSON)     # [{name, level, years, category}]
    target_role = Column(String(200))
    years_experience = Column(Integer, default=0)
    location = Column(String(200))
    languages = Column(JSON)          # ["Portuguese", "English"]
    memory_file = Column(String(500)) # Path to persistent memory JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    skill_progress = relationship("SkillProgress", back_populates="user", cascade="all, delete-orphan")
    learning_sessions = relationship("LearningSession", back_populates="user", cascade="all, delete-orphan")
