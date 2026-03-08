import os

ANSWER_MODEL = os.getenv("ANSWER_MODEL", "llama3.2:latest")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
