"""Fixture adapter. Tests pass a map of input text to JSON. No network."""

from llm.protocol import CompletionRequest, CompletionResult, LanguageModelError


class FakeLanguageModel:
    def __init__(self, fixtures: dict[str, dict[str, object]] | None = None) -> None:
        self.fixtures = fixtures or {}

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        if request.input in self.fixtures:
            return CompletionResult.model_validate({"json": self.fixtures[request.input]})
        raise LanguageModelError("no fixture for this input")
