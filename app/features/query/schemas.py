from typing import List, Literal, Optional, Union
from typing import Annotated

from pydantic import BaseModel, Field


class QueryIn(BaseModel):
    prompt: str


class ChatTitleMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatTitleIn(BaseModel):
    messages: List[ChatTitleMessage]


class ChatTitleOut(BaseModel):
    title: Optional[str]


class Hit(BaseModel):
    text: str
    filename: str
    zotero_id: str
    chunk_index: int


class Source(BaseModel):
    id: str
    filename: str
    zotero_id: str


class QueryUpdateProgressEvent(BaseModel):
    type: Literal["updateProgress"] = "updateProgress"
    stage: str
    debug: Optional[str] = None


class SetSourcesEvent(BaseModel):
    type: Literal["setSources"] = "setSources"
    sources: List[Source]


class TokenEvent(BaseModel):
    type: Literal["token"] = "token"
    token: str


class QueryDoneEvent(BaseModel):
    type: Literal["done"] = "done"


QueryNDJSONEvent = Annotated[
    Union[QueryUpdateProgressEvent, SetSourcesEvent, TokenEvent, QueryDoneEvent],
    Field(discriminator="type"),
]


def ndjson_query(event: QueryNDJSONEvent) -> str:
    return event.model_dump_json() + "\n"
