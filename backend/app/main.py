import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError

from .database import Base, engine
from .routers import services

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s level=%(levelname)s logger=%(name)s msg=%(message)s",
)
logger = logging.getLogger("servicepulse")


def init_db():
    """Create tables on boot, retrying briefly. This tolerates the MySQL
    container/RDS instance not being reachable yet on the very first
    start (a small, cheap piece of 'reliability under failure')."""
    last_error = None
    for attempt in range(1, 6):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("database ready (attempt %s)", attempt)
            return
        except OperationalError as exc:
            last_error = exc
            logger.warning("database not ready (attempt %s/5): %s", attempt, exc)
            time.sleep(2)
    logger.error("could not reach the database after 5 attempts: %s", last_error)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="ServicePulse", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(services.router)


@app.get("/health")
def health():
    return {"status": "healthy"}


# Registered LAST on purpose: this is a catch-all for "/", so anything
# above it (/services, /health, FastAPI's own /docs) is matched first.
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
