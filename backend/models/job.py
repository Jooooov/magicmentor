from sqlalchemy import Column, Integer, String, Text, Float, DateTime, JSON, Boolean, ForeignKey
from datetime import datetime
from ..database import Base


class JobPosting(Base):
    __tablename__ = "job_postings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=True)
    title = Column(String(300))
    company = Column(String(200))
    location = Column(String(200))
    description = Column(Text)
    required_skills = Column(JSON)       # Extracted skills list
    salary_min = Column(Float)
    salary_max = Column(Float)
    url = Column(String(500))
    source = Column(String(100))         # linkedin, indeed, glassdoor, etc.
    is_remote = Column(Boolean, default=False)
    date_posted = Column(String(50))
    # Match scores (populated after AI analysis)
    match_score = Column(Float)          # 0-100 current match
    potential_match_score = Column(Float) # 0-100 after learning
    matching_skills = Column(JSON)
    missing_skills = Column(JSON)
    quick_wins = Column(JSON)
    recommendation = Column(String(100))  # "Apply now" | "Apply after upskilling"
    scraped_at = Column(DateTime, default=datetime.utcnow)
