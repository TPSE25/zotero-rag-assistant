from fastapi import APIRouter, HTTPException

from features.prompts.schemas import (
    SystemPromptListOut,
    SystemPromptOut,
    UpdateSystemPromptIn,
)
from features.prompts.store import (
    UnknownPromptKeyError,
    list_prompts,
    update_prompt_content,
)

router = APIRouter(tags=["prompts"])


@router.get("/api/system-prompts", response_model=SystemPromptListOut)
async def get_system_prompts() -> SystemPromptListOut:
    return SystemPromptListOut.model_validate({"prompts": list_prompts()})


@router.put("/api/system-prompts/{prompt_key}", response_model=SystemPromptOut)
async def put_system_prompt(
    prompt_key: str,
    body: UpdateSystemPromptIn,
) -> SystemPromptOut:
    try:
        update_prompt_content(prompt_key, body.content)
        prompt = next((p for p in list_prompts() if p["key"] == prompt_key), None)
        if prompt is None:
            raise HTTPException(status_code=404, detail=f"Prompt key not found: {prompt_key}")
        return SystemPromptOut.model_validate(prompt)
    except UnknownPromptKeyError:
        raise HTTPException(status_code=404, detail=f"Prompt key not found: {prompt_key}")
