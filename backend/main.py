from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .api.routes import profile, mentor, learning, jobs

# Init DB tables on startup
init_db()

app = FastAPI(
    title="MagicMentor API",
    description="AI-powered career mentoring, skill development & job matching",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profile.router, prefix="/api/v1/profile", tags=["Profile"])
app.include_router(mentor.router,  prefix="/api/v1/mentor",  tags=["Mentor"])
app.include_router(learning.router, prefix="/api/v1/learning", tags=["Learning"])
app.include_router(jobs.router,    prefix="/api/v1/jobs",    tags=["Jobs"])


@app.get("/")
def root():
    return {
        "name": "MagicMentor API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "profile":  "/api/v1/profile",
            "mentor":   "/api/v1/mentor",
            "learning": "/api/v1/learning",
            "jobs":     "/api/v1/jobs",
        },
    }


@app.get("/health")
def health():
    return {"status": "healthy"}
