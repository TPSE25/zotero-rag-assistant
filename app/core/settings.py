import os


def _get_int(name: str, default: int, minimum: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        value = default
    else:
        value = int(raw)
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


def _get_optional_float(name: str, minimum: float | None = None) -> float | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    stripped = raw.strip()
    if stripped == "":
        return None
    value = float(stripped)
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


ANSWER_MODEL = os.getenv("ANSWER_MODEL", "llama3.2:latest")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
MAX_OLLAMA_PARALLEL_CALLS = _get_int("MAX_OLLAMA_PARALLEL_CALLS", 4, minimum=1)
ANNOTATION_DEFAULT_CHUNK_SIZE = _get_int("ANNOTATION_DEFAULT_CHUNK_SIZE", 1600, minimum=32)
QUERY_N_RESULTS = _get_int("QUERY_N_RESULTS", 12, minimum=1)
QUERY_NEIGHBOR_TOP_N = _get_int("QUERY_NEIGHBOR_TOP_N", 5, minimum=0)
QUERY_NEIGHBOR_DISTANCE_THRESHOLD = _get_optional_float(
    "QUERY_NEIGHBOR_DISTANCE_THRESHOLD",
    minimum=0.0,
)
