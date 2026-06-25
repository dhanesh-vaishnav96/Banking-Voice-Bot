"""
Hindi Voice Collection Bot — FastAPI Application Entry Point

Run with:
    uvicorn backend.main:app --reload --port 8000
"""

import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.routes.conversation import router as conversation_router
from backend.config import AUDIO_DIR, HOST, PORT

# ─── Logging Setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Hindi Voice Collection Bot",
    description=(
        "A Human-Like Hindi Voice Bot for loan/payment collection. "
        "Uses rule-based conversation engine with edge-tts for natural Hindi speech."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routes ────────────────────────────────────────────────────────────────────
app.include_router(conversation_router)

# ─── Static Files ──────────────────────────────────────────────────────────────
# Serve generated audio files
app.mount("/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")

# Serve frontend static files
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        """Serve the frontend index.html at root URL."""
        index_path = FRONTEND_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"message": "Frontend not found. Access API at /docs"}
else:
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "message": "Hindi Voice Collection Bot API",
            "docs": "/docs",
            "health": "/api/health",
        }


# ─── Startup / Shutdown Events ─────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("Hindi Voice Collection Bot Starting...")
    logger.info(f"Audio directory: {AUDIO_DIR}")
    logger.info(f"Frontend directory: {FRONTEND_DIR}")
    logger.info("API Docs available at: http://localhost:8000/docs")
    logger.info("Frontend available at: http://localhost:8000/")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Hindi Voice Collection Bot shutting down.")


# ─── Dev Server Entry Point ────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=HOST,
        port=PORT,
        reload=True,
        log_level="info",
    )
