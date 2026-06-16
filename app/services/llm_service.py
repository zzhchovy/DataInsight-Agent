from dataclasses import dataclass
import os

import httpx

from app.core.config import get_settings


@dataclass(frozen=True)
class LLMContext:
    label: str
    source: str
    content: str
    page: int | None = None


@dataclass(frozen=True)
class LLMResult:
    text: str
    used_llm: bool
    provider: str | None = None
    model: str | None = None
    error: str | None = None


def generate_rag_answer(question: str, contexts: list[LLMContext]) -> LLMResult:
    settings = get_settings()
    provider = settings.llm_provider.lower().strip()

    if provider in {"", "none", "disabled", "off"}:
        return LLMResult(
            text="未启用外部大模型，已回退到本地检索片段式回答。",
            used_llm=False,
            provider=provider or "none",
            model=None,
        )

    if provider in {"openai", "openai_compatible"}:
        return _call_openai_compatible(question=question, contexts=contexts)

    return LLMResult(
        text=f"暂不支持的 LLM provider：{settings.llm_provider}",
        used_llm=False,
        provider=settings.llm_provider,
        model=settings.llm_model,
        error=f"Unsupported provider: {settings.llm_provider}",
    )


def _call_openai_compatible(question: str, contexts: list[LLMContext]) -> LLMResult:
    settings = get_settings()
    api_key = settings.llm_api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return LLMResult(
            text="已配置 LLM provider，但没有找到 API Key，因此回退到本地检索片段式回答。",
            used_llm=False,
            provider=settings.llm_provider,
            model=settings.llm_model,
            error="Missing API key",
        )

    messages = _build_rag_messages(question=question, contexts=contexts)
    url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": 0.2,
    }

    try:
        response = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"]["content"].strip()
        return LLMResult(
            text=text,
            used_llm=True,
            provider=settings.llm_provider,
            model=settings.llm_model,
        )
    except Exception as exc:
        return LLMResult(
            text="调用外部大模型失败，已回退到本地检索片段式回答。",
            used_llm=False,
            provider=settings.llm_provider,
            model=settings.llm_model,
            error=str(exc),
        )


def _build_rag_messages(question: str, contexts: list[LLMContext]) -> list[dict[str, str]]:
    context_text = "\n\n".join(_format_context(context) for context in contexts)
    return [
        {
            "role": "system",
            "content": (
                "你是 DataInsight-Agent 的 RAG 回答模块。"
                "请严格基于用户提供的检索片段回答问题，不要编造未出现的信息。"
                "回答必须使用中文。"
                "每个关键结论后尽量标注对应引用，例如 [来源1]、[来源2]。"
                "如果证据不足，请明确说明不确定性。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"用户问题：{question}\n\n"
                f"检索片段：\n{context_text}\n\n"
                "请输出：\n"
                "1. 直接回答；\n"
                "2. 依据说明；\n"
                "3. 不确定性或需要补充的数据。"
            ),
        },
    ]


def _format_context(context: LLMContext) -> str:
    page_text = f"，页码：{context.page}" if context.page is not None else ""
    return (
        f"[{context.label}]\n"
        f"来源文件：{context.source}{page_text}\n"
        f"内容：{context.content}"
    )
