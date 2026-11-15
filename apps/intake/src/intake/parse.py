from contracts.drafts import ParseRequest, ParseResponse
from llm.fake import FakeLanguageModel
from llm.protocol import CompletionRequest, LanguageModel, LanguageModelError

from intake.phrases import match_fixed_phrase
from intake.prompts import EXTRACTION_SCHEMA, INSTRUCTIONS
from intake.resolve import question, resolve_extraction
from intake.settings import Settings


class IntakeUnavailable(Exception):
    pass


async def parse_sentence(
    request: ParseRequest,
    settings: Settings,
    model: LanguageModel,
) -> ParseResponse:
    if settings.llm_provider == "openai" and not settings.llm_api_key:
        raise IntakeUnavailable("llm key is empty")
    tokens = {child.token: child.id for child in request.children}
    extraction: dict[str, object] | None = None
    if isinstance(model, FakeLanguageModel) and request.text in model.fixtures:
        extraction = model.fixtures[request.text]
    elif settings.llm_provider == "fake":
        extraction = match_fixed_phrase(request.text)
        if extraction is None:
            return ParseResponse(
                status="needs_clarification",
                questions=[question(request.locale_hint, "unsupported")],
            )
    else:
        try:
            result = await model.complete(
                CompletionRequest(
                    purpose="intake",
                    schema_name="event_extraction",
                    json_schema=EXTRACTION_SCHEMA,
                    instructions=INSTRUCTIONS,
                    input=request.text,
                )
            )
        except LanguageModelError as exc:
            raise IntakeUnavailable("model failed") from exc
        extraction = result.json_data
    if not isinstance(extraction, dict):
        raise IntakeUnavailable("model json was not an object")
    return resolve_extraction(extraction, request.now, request.locale_hint, tokens)
