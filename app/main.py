import logging
import sys

from fastapi import FastAPI

from core.startup import startup_event
from features.annotations.router import router as annotations_router
from features.health.router import router as health_router
from features.ingest.router import router as ingest_router
from features.prompts.router import router as prompts_router
from features.query.router import router as query_router

logging.basicConfig(
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
)

app = FastAPI()
app.add_event_handler("startup", startup_event)

app.include_router(health_router)
app.include_router(query_router)
app.include_router(prompts_router)
app.include_router(ingest_router)
app.include_router(annotations_router)
