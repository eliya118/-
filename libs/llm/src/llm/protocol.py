from typing import Literal, Protocol

from pydantic import BaseModel, Field


class CompletionRequest(BaseModel):
    purpose: Literal["intake", "activities", "meals"]
    schema_name: str
    json_schema: dict[str, object]
    instructions: str
    input: str


class CompletionResult(BaseModel):
    json_data: dict[str, object] = Field(alias="json")

    model_config = {"populate_by_name": True}


class LanguageModelError(Exception):
    """Schema failure or transport failure from a vendor adapter."""


class LanguageModel(Protocol):
    async def complete(self, request: CompletionRequest) -> CompletionResult:
        """Return parsed JSON. Raise LanguageModelError on failure."""
        ...
