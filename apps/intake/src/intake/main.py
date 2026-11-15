import hmac
import logging
import uuid
from contextlib import asynccontextmanager

from contracts.drafts import ParseRequest
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from llm.fake import FakeLanguageModel
from llm.openai import OpenAILanguageModel
from llm.protocol import LanguageModel

from intake.logging import configure_logging, request_id_var
from intake.parse import IntakeUnavailable, parse_sentence
from intake.settings import Settings

log = logging.getLogger("intake")


def build_model(settings: Settings) -> LanguageModel:
    if settings.llm_provider == "openai":
        return OpenAILanguageModel(api_key=settings.llm_api_key, model=settings.llm_model)
    return FakeLanguageModel()


def create_app(settings: Settings | None = None, model: LanguageModel | None = None) -> FastAPI:
    settings = settings or Settings()  # type: ignore[call-arg]
    configure_logging(settings.log_level)
    language_model = model or build_model(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.model = language_model
        yield

    app = FastAPI(title="intake", lifespan=lifespan)
    app.state.settings = settings
    app.state.model = language_model

    def authorized(authorization: str | None) -> bool:
        token = ""
        if authorization and authorization.startswith("Bearer "):
            token = authorization.removeprefix("Bearer ")
        return hmac.compare_digest(token, settings.internal_api_token)

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        incoming = request.headers.get("x-request-id") or str(uuid.uuid4())
        token = request_id_var.set(incoming)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = incoming
            return response
        finally:
            request_id_var.reset(token)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/internal/parse")
    async def parse(
        body: ParseRequest,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        if not authorized(authorization):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        try:
            result = await parse_sentence(body, settings, app.state.model)
        except IntakeUnavailable:
            log.warning("parse unavailable")
            return JSONResponse({"error": "unavailable"}, status_code=503)
        return JSONResponse(result.model_dump(mode="json"))

    return app


app = create_app()
