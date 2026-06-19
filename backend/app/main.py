"""
Brieflyy — FastAPI Application Entry Point
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import auth, cv, search, strategy, jobs, tailoring
from app.middleware.error_handler import register_error_handlers
from app.services.redis_service import redis_service


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle events."""
    await redis_service.connect()
    await init_db()
    logger.info("Brieflyy API started (GCP enabled: %s)", settings.gcp_enabled)
    yield
    from app.services.job_aggregator import job_aggregator
    await job_aggregator.close()
    await redis_service.close()


app = FastAPI(
    title="Brieflyy API",
    description="AI-powered job search reasoning system for students and early-career professionals",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register error handlers
register_error_handlers(app)

# Register routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(cv.router, prefix="/cv", tags=["CV Management"])
app.include_router(search.router, prefix="/search", tags=["Job Search"])
app.include_router(strategy.router, prefix="/strategy", tags=["Strategy"])
app.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
app.include_router(tailoring.router, prefix="/tailor", tags=["CV Tailoring"])


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "brieflyy-api"}
