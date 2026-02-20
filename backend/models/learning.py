from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from ..database import Base


class LearningSession(Base):
    __tablename__ = "learning_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_profiles.id"))
    skill_name = Column(String(200))
    user_level = Column(String(50), default="beginner")
    messages = Column(JSON, default=list)  # Full conversation history
    status = Column(String(50), default="active")  # active, completed, paused
    score = Column(Float)              # 0-100 comprehension score
    concepts_covered = Column(JSON, default=list)
    started_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)

    user = relationship("UserProfile", back_populates="learning_sessions")
