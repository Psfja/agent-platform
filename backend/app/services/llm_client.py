from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import get_settings
from app.core.errors import AppError


@dataclass(slots=True)
class LLMResult:
    data: dict[str, Any]
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw_content: str = ""


class ChatModel(Protocol):
    model: str

    def chat_json(self, system: str, user: str, *, temperature: float = 0.1) -> LLMResult: ...


class OpenAICompatibleClient:
    """Minimal OpenAI-compatible client for One API, LiteLLM, DeepSeek and Qwen."""

    def __init__(self, *, base_url: str | None = None, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self.model = model or settings.llm_model
        self.timeout = settings.llm_timeout_seconds
        self.max_retries = settings.llm_max_retries

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "provider": "openai-compatible",
            "base_url": self.base_url,
            "model": self.model,
            "timeout_seconds": self.timeout,
            "supports_real_execution": self.configured,
            "message": "模型网关已配置，可执行真实 Agent。" if self.configured else "尚未配置 LLM_API_KEY；请写入 backend/.env 后重启 API。",
        }

    def chat_json(self, system: str, user: str, *, temperature: float = 0.1) -> LLMResult:
        if not self.configured:
            raise AppError(503, "LLM_NOT_CONFIGURED", "真实 Agent 需要配置 LLM_API_KEY", {"env": ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"]})
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self._request(payload)
                body = response.json()
                content = body["choices"][0]["message"]["content"]
                parsed = parse_json_object(content)
                usage = body.get("usage", {})
                return LLMResult(
                    data=parsed,
                    prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
                    completion_tokens=int(usage.get("completion_tokens", 0) or 0),
                    raw_content=content,
                )
            except httpx.HTTPStatusError as exc:
                last_error = exc
                # Some OpenAI-compatible providers do not support response_format.
                if exc.response.status_code == 400 and "response_format" in payload:
                    payload.pop("response_format", None)
                elif attempt >= self.max_retries:
                    detail = exc.response.text[:1000]
                    raise AppError(502, "LLM_REQUEST_FAILED", "模型网关请求失败", {"status": exc.response.status_code, "response": detail}) from exc
            except (httpx.HTTPError, KeyError, TypeError, json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise AppError(502, "LLM_RESPONSE_INVALID", "模型响应不是有效的结构化 JSON", {"error": str(exc)}) from exc
            time.sleep(min(2 ** attempt, 5))
        raise AppError(502, "LLM_REQUEST_FAILED", "模型请求失败", {"error": str(last_error)})

    def _request(self, payload: dict[str, Any]) -> httpx.Response:
        with httpx.Client(timeout=httpx.Timeout(self.timeout, connect=20)) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            return response


def parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("response does not contain a JSON object")
        text = text[start : end + 1]
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError("response root must be an object")
    return result
