from typing import List

from pydantic import BaseModel


class PromptPlaceholderOut(BaseModel):
    name: str
    description: str


class SystemPromptOut(BaseModel):
    key: str
    title: str
    description: str
    placeholders: List[PromptPlaceholderOut]
    content: str


class SystemPromptListOut(BaseModel):
    prompts: List[SystemPromptOut]


class UpdateSystemPromptIn(BaseModel):
    content: str
