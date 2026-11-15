"""OpenAI adapter. The model id is passed in; nothing here hard-codes one."""

import json

import httpx

from llm.protocol import CompletionRequest, CompletionResult, LanguageModelError


class OpenAILanguageModel:
    def __init__(self, api_key: str, model: str, base_url: str = "https://api.openai.com/v1") -> None:
        if not model:
            raise LanguageModelError("LLM_MODEL is empty")
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        if not self._api_key:
            raise LanguageModelError("LLM_API_KEY is empty")
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": request.instructions},
                {"role": "user", "content": request.input},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "schema": request.json_schema,
                    "strict": True,
                },
            },
        }
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=body,
                )
        except httpx.HTTPError as exc:
            raise LanguageModelError("openai transport failed") from exc
        if response.status_code >= 400:
            raise LanguageModelError(f"openai status {response.status_code}")
        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LanguageModelError("openai response was not valid json") from exc
        if not isinstance(parsed, dict):
            raise LanguageModelError("openai response was not an object")
        return CompletionResult.model_validate({"json": parsed})
