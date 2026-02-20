from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from ..database import Base


class SkillProgress(Base):
    __tablename__ = "skill_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_profiles.id"))
    skill_name = Column(String(200))
    category = Column(String(100))       # programming, framework, tool, cloud, soft_skill
    level = Column(String(50))           # beginner, intermediate, advanced
    status = Column(String(50))          # current, learning, target, completed
    priority = Column(Integer, default=99)
    market_demand = Column(String(50))   # high, medium, low
    match_boost = Column(Float, default=0.0)  # % improvement in job matches
    learning_score = Column(Float)       # 0-100 from Q&A validation
    estimated_time = Column(String(50))  # "2 weeks"
    resources = Column(String(1000))     # Comma-separated resources
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("UserProfile", back_populates="skill_progress")
