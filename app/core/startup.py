import logging

from core.clients import ensure_model_installed
from core.settings import ANSWER_MODEL, EMBEDDING_MODEL
from features.prompts.store import ensure_prompt_store


async def startup_event() -> None:
    ensure_prompt_store()
    answer_model_installed = await ensure_model_installed(ANSWER_MODEL)
    embedding_model_installed = await ensure_model_installed(EMBEDDING_MODEL)
    if not answer_model_installed:
        logging.warning(f"Failed to install answer model: {ANSWER_MODEL}")
    if not embedding_model_installed:
        logging.warning(f"Failed to install embedding model: {EMBEDDING_MODEL}")
