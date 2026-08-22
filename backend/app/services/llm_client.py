from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Iterator, Protocol

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

    def chat(self, system: str, messages: list[dict[str, str]], *, temperature: float = 0.3) -> str:
        """普通对话补全（非 JSON 模式），返回模型文本回复。"""
        if not self.configured:
            raise AppError(503, "LLM_NOT_CONFIGURED", "真实对话需要配置 LLM_API_KEY", {"env": ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"]})
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}] + messages,
            "temperature": temperature,
        }
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self._request(payload)
                body = response.json()
                return str(body["choices"][0]["message"]["content"] or "").strip()
            except (httpx.HTTPError, KeyError, TypeError, json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise AppError(502, "LLM_RESPONSE_INVALID", "模型对话响应无效", {"error": str(exc)}) from exc
            time.sleep(min(2 ** attempt, 5))
        raise AppError(502, "LLM_REQUEST_FAILED", "模型请求失败", {"error": str(last_error)})

    def chat_stream(self, system: str, messages: list[dict[str, str]], *, temperature: float = 0.3) -> Iterator[str]:
        """流式对话补全，逐块产出文本；提供方不支持 stream 时自动降级为整段返回。"""
        if not self.configured:
            raise AppError(503, "LLM_NOT_CONFIGURED", "真实对话需要配置 LLM_API_KEY", {"env": ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"]})
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}] + messages,
            "temperature": temperature,
            "stream": True,
        }
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=httpx.Timeout(self.timeout, connect=20)) as client:
                    with client.stream("POST", f"{self.base_url}/chat/completions", headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, json=payload) as response:
                        if response.status_code == 400 and "stream" in payload:
                            # 提供方不支持流式：降级为非流式整段返回
                            full = self.chat(system, messages, temperature=temperature)
                            yield full
                            return
                        response.raise_for_status()
                        produced = False
                        for line in response.iter_lines():
                            line = line.strip()
                            if not line.startswith("data:"):
                                continue
                            data = line[5:].strip()
                            if data == "[DONE]":
                                return
                            try:
                                obj = json.loads(data)
                                delta = obj["choices"][0]["delta"].get("content")
                                if delta:
                                    produced = True
                                    yield delta
                            except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                                continue
                        if not produced:
                            raise AppError(502, "LLM_RESPONSE_INVALID", "模型流式响应为空")
                        return
            except AppError:
                raise
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise AppError(502, "LLM_STREAM_FAILED", "模型流式请求失败", {"error": str(exc)}) from exc
            time.sleep(min(2 ** attempt, 5))
        raise AppError(502, "LLM_STREAM_FAILED", "模型流式请求失败", {"error": str(last_error)})

    def _request(self, payload: dict[str, Any]) -> httpx.Response:
        with httpx.Client(timeout=httpx.Timeout(self.timeout, connect=20)) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            return response


def estimate_tokens(text: str) -> int:
    """粗略估算文本 Token 数：中日韩字符按 1，其余按 4 字符 1 Token。"""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = len(text) - cjk
    return max(1, int(cjk + other / 4))


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
