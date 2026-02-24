from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class PromptPlaceholder:
    name: str
    description: str


@dataclass(frozen=True)
class PromptSpec:
    key: str
    filename: str
    title: str
    description: str
    placeholders: tuple[PromptPlaceholder, ...]


PROMPTS_DIR = Path(os.getenv("PROMPTS_DIR", "/prompts"))
DEFAULT_PROMPTS_DIR = Path(__file__).resolve().parent / "default_prompts"


PROMPT_SPECS: dict[str, PromptSpec] = {
    "query_system": PromptSpec(
        key="query_system",
        filename="query_system.txt",
        title="Query System Prompt",
        description="Used for normal RAG question answering.",
        placeholders=(),
    ),
    "title_system": PromptSpec(
        key="title_system",
        filename="title_system.txt",
        title="Chat Title System Prompt",
        description="Used to generate short chat titles.",
        placeholders=(),
    ),
    "annotation_coarse_user": PromptSpec(
        key="annotation_coarse_user",
        filename="annotation_coarse_user.txt",
        title="Annotation Coarse Match Prompt",
        description="Selects candidate sentence IDs for each rule.",
        placeholders=(
            PromptPlaceholder("rule_descriptions", "List of rule IDs and text."),
            PromptPlaceholder("sentence_block", "Sentence IDs and sentence text."),
        ),
    ),
    "annotation_boundary_user": PromptSpec(
        key="annotation_boundary_user",
        filename="annotation_boundary_user.txt",
        title="Annotation Boundary Prompt",
        description="Refines a candidate token range to exact boundaries.",
        placeholders=(
            PromptPlaceholder("rule_id", "ID of the active rule."),
            PromptPlaceholder("rule_terms", "Rule text/terms."),
            PromptPlaceholder("plain_text", "Candidate plain text for the range."),
            PromptPlaceholder("token_lines", "Indexed token lines for the range."),
        ),
    ),
}


class UnknownPromptKeyError(ValueError):
    pass


class MissingPlaceholderError(ValueError):
    pass


def _get_spec(prompt_key: str) -> PromptSpec:
    spec = PROMPT_SPECS.get(prompt_key)
    if spec is None:
        raise UnknownPromptKeyError(f"Unknown prompt key: {prompt_key}")
    return spec


def _default_path(prompt_key: str) -> Path:
    return DEFAULT_PROMPTS_DIR / _get_spec(prompt_key).filename


def _prompt_path(prompt_key: str) -> Path:
    return PROMPTS_DIR / _get_spec(prompt_key).filename


def ensure_prompt_store() -> None:
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    for key in PROMPT_SPECS:
        target = _prompt_path(key)
        if target.exists():
            continue
        src = _default_path(key)
        if not src.exists():
            raise FileNotFoundError(f"Missing default prompt file: {src}")
        shutil.copyfile(src, target)


def get_prompt_content(prompt_key: str) -> str:
    ensure_prompt_store()
    path = _prompt_path(prompt_key)
    if not path.exists():
        src = _default_path(prompt_key)
        shutil.copyfile(src, path)
    return path.read_text(encoding="utf-8")


def update_prompt_content(prompt_key: str, content: str) -> None:
    ensure_prompt_store()
    _prompt_path(prompt_key).write_text(content, encoding="utf-8")


def render_prompt(prompt_key: str, values: Mapping[str, str]) -> str:
    text = get_prompt_content(prompt_key)
    spec = _get_spec(prompt_key)
    out = text
    for placeholder in spec.placeholders:
        token = f"{{{{{placeholder.name}}}}}"
        if placeholder.name not in values:
            raise MissingPlaceholderError(
                f"Missing placeholder '{placeholder.name}' for prompt '{prompt_key}'"
            )
        out = out.replace(token, values[placeholder.name])
    return out


def list_prompts() -> list[dict[str, object]]:
    ensure_prompt_store()
    out: list[dict[str, object]] = []
    for key, spec in PROMPT_SPECS.items():
        out.append(
            {
                "key": key,
                "title": spec.title,
                "description": spec.description,
                "placeholders": [
                    {"name": p.name, "description": p.description}
                    for p in spec.placeholders
                ],
                "content": get_prompt_content(key),
            }
        )
    return out
