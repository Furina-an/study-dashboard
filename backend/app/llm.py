"""OpenAI 兼容 LLM 调用与 JSON 解析（ai 配置与计划 AI 拆解共用）。"""
import json
import os
import re

import httpx

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"


def env_config() -> dict:
    """读取服务器环境变量配置，未设置 key 时返回空 key。"""
    base_url = os.getenv("LLM_API_BASE", "").strip() or DEFAULT_BASE_URL
    model = os.getenv("LLM_MODEL", "").strip() or DEFAULT_MODEL
    api_key = os.getenv("LLM_API_KEY", "").strip()
    return {"base_url": base_url.rstrip("/"), "model": model, "api_key": api_key}


def chat_completion(
    base_url: str,
    model: str,
    api_key: str,
    messages: list[dict],
    timeout: float = 60.0,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> str:
    """调用 /chat/completions，返回首个回复文本；失败抛 httpx.HTTPError。"""
    payload: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    resp = httpx.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def extract_error_message(exc: Exception) -> str:
    """把调用异常转成用户可读的中文提示。"""
    if isinstance(exc, httpx.HTTPStatusError):
        detail = ""
        try:
            body = exc.response.json()
            if isinstance(body, dict):
                err = body.get("error")
                if isinstance(err, dict):
                    detail = str(err.get("message", ""))
                else:
                    detail = str(body.get("message", ""))
        except Exception:
            detail = exc.response.text[:200]
        return f"接口返回 {exc.response.status_code}：{detail or '未知错误'}"
    if isinstance(exc, httpx.HTTPError):
        return f"网络错误：{exc}"
    return f"调用失败：{exc}"


def parse_children_json(content: str) -> list[dict]:
    """解析 LLM 返回的 {children:[...]}，兼容 markdown 代码块包裹。"""
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return []
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []

    items = data.get("children") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []

    result: list[dict] = []
    for item in items:
        if isinstance(item, dict) and item.get("title"):
            result.append(
                {
                    "title": str(item["title"])[:100],
                    "description": str(item.get("description", ""))[:500],
                }
            )
        elif isinstance(item, str) and item.strip():
            result.append({"title": item.strip()[:100], "description": ""})
    return result
