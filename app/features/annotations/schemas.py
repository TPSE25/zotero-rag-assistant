from typing import Any, Dict, List, Literal, Optional, Union
from typing import Annotated

from pydantic import BaseModel, Field


class RagPdfMatch(BaseModel):
    id: str
    pageIndex: int = Field(ge=0)
    rects: List[List[float]]
    text: str | None = None


class AnnotationsResponse(BaseModel):
    matches: List[RagPdfMatch]
    llmDebug: List[Dict[str, Any]] = Field(default_factory=list)


class RagHighlightRule(BaseModel):
    id: str
    termsRaw: str


class RagPopupConfig(BaseModel):
    rules: list[RagHighlightRule]
    chunkLength: int | None = Field(default=None, ge=32, le=20000)
    pageRange: str | None = None


class AnnotationUpdateProgressEvent(BaseModel):
    type: Literal["updateProgress"] = "updateProgress"
    stage: str
    debug: Optional[str] = None
    sent: Optional[int] = None
    chunk: Optional[int] = None
    marker: Optional[int] = None
    markerTotal: Optional[int] = None
    markerId: Optional[str] = None
    completed: Optional[int] = None
    total: Optional[int] = None


class AnnotationDoneEvent(BaseModel):
    type: Literal["done"] = "done"


class AnnotationMatchesEvent(BaseModel):
    type: Literal["annotationMatches"] = "annotationMatches"
    matches: List[Dict[str, Any]]


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


AnnotationNDJSONEvent = Annotated[
    Union[
        AnnotationUpdateProgressEvent,
        AnnotationMatchesEvent,
        AnnotationDoneEvent,
        ErrorEvent,
    ],
    Field(discriminator="type"),
]


def ndjson_annotation(event: AnnotationNDJSONEvent) -> str:
    return event.model_dump_json() + "\n"
