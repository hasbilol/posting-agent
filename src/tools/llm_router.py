"""Multi-provider Free LLM Router.

Mirrors FreeLLMAPI's routing strategy across multiple free providers and custom endpoints.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LLMRouter:
    """Multi-provider fallback LLM router for zero-cost execution."""

    def __init__(self) -> None:
        pass

    def invoke(self, prompt: str) -> str:
        """Invoke LLM with automatic fallback across all available providers."""
        errors: list[str] = []

        # 0. Custom OpenAI-compatible endpoint (e.g. local FreeLLMAPI: http://127.0.0.1:31415/v1)
        custom_base = os.getenv("LLM_BASE_URL", "")
        custom_key = os.getenv("LLM_API_KEY", "")
        if custom_base:
            try:
                from langchain_openai import ChatOpenAI

                llm = ChatOpenAI(
                    model=os.getenv("LLM_MODEL", "auto"),
                    api_key=custom_key or "sk-dummy",
                    base_url=custom_base,
                )
                resp = llm.invoke(prompt)
                content = str(resp.content).strip() if hasattr(resp, "content") else str(resp).strip()
                if content:
                    logger.info("LLM Router succeeded using Custom Endpoint: %s", custom_base)
                    return content
            except Exception as exc:
                errors.append(f"Custom endpoint error: {exc}")
                logger.warning("Custom endpoint failed, trying next provider: %s", exc)

        # 1. Google AI Studio (Gemini)
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if gemini_key:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI

                llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", api_key=gemini_key)
                resp = llm.invoke(prompt)
                content = str(resp.content).strip() if hasattr(resp, "content") else str(resp).strip()
                if content:
                    logger.info("LLM Router succeeded using: Google AI Studio (Gemini)")
                    return content
            except Exception as exc:
                errors.append(f"Google AI Studio error: {exc}")
                logger.warning("Google AI Studio failed: %s", exc)

        # 2. Groq
        groq_key = os.getenv("GROQ_API_KEY", "")
        if groq_key:
            try:
                from langchain_openai import ChatOpenAI

                llm = ChatOpenAI(
                    model="llama-3.3-70b-versatile",
                    api_key=groq_key,
                    base_url="https://api.groq.com/openai/v1",
                )
                resp = llm.invoke(prompt)
                content = str(resp.content).strip() if hasattr(resp, "content") else str(resp).strip()
                if content:
                    logger.info("LLM Router succeeded using: Groq")
                    return content
            except Exception as exc:
                errors.append(f"Groq error: {exc}")
                logger.warning("Groq failed: %s", exc)

        # 3. OpenRouter
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        if openrouter_key:
            try:
                from langchain_openai import ChatOpenAI

                llm = ChatOpenAI(
                    model="deepseek/deepseek-chat",
                    api_key=openrouter_key,
                    base_url="https://openrouter.ai/api/v1",
                )
                resp = llm.invoke(prompt)
                content = str(resp.content).strip() if hasattr(resp, "content") else str(resp).strip()
                if content:
                    logger.info("LLM Router succeeded using: OpenRouter")
                    return content
            except Exception as exc:
                errors.append(f"OpenRouter error: {exc}")
                logger.warning("OpenRouter failed: %s", exc)

        # 4. NVIDIA NIM
        nvidia_key = os.getenv("NVIDIA_API_KEY", "")
        if nvidia_key:
            try:
                from langchain_openai import ChatOpenAI

                llm = ChatOpenAI(
                    model="meta/llama-3.3-70b-instruct",
                    api_key=nvidia_key,
                    base_url="https://integrate.api.nvidia.com/v1",
                )
                resp = llm.invoke(prompt)
                content = str(resp.content).strip() if hasattr(resp, "content") else str(resp).strip()
                if content:
                    logger.info("LLM Router succeeded using: NVIDIA NIM")
                    return content
            except Exception as exc:
                errors.append(f"NVIDIA NIM error: {exc}")
                logger.warning("NVIDIA NIM failed: %s", exc)

        # 5. Cohere
        cohere_key = os.getenv("COHERE_API_KEY", "")
        if cohere_key:
            try:
                from langchain_openai import ChatOpenAI

                llm = ChatOpenAI(
                    model="command-r-plus",
                    api_key=cohere_key,
                    base_url="https://api.cohere.ai/v1",
                )
                resp = llm.invoke(prompt)
                content = str(resp.content).strip() if hasattr(resp, "content") else str(resp).strip()
                if content:
                    logger.info("LLM Router succeeded using: Cohere")
                    return content
            except Exception as exc:
                errors.append(f"Cohere error: {exc}")
                logger.warning("Cohere failed: %s", exc)

        # 6. Zhipu AI (Z.ai)
        zhipu_key = os.getenv("ZHIPU_API_KEY", "")
        if zhipu_key:
            try:
                from langchain_openai import ChatOpenAI

                llm = ChatOpenAI(
                    model="glm-4-flash",
                    api_key=zhipu_key,
                    base_url="https://open.bigmodel.cn/api/paas/v4",
                )
                resp = llm.invoke(prompt)
                content = str(resp.content).strip() if hasattr(resp, "content") else str(resp).strip()
                if content:
                    logger.info("LLM Router succeeded using: Zhipu AI")
                    return content
            except Exception as exc:
                errors.append(f"Zhipu AI error: {exc}")
                logger.warning("Zhipu AI failed: %s", exc)

        # 7. DeepSeek
        deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
        if deepseek_key:
            try:
                from langchain_openai import ChatOpenAI

                llm = ChatOpenAI(
                    model="deepseek-chat",
                    api_key=deepseek_key,
                    base_url="https://api.deepseek.com/v1",
                )
                resp = llm.invoke(prompt)
                content = str(resp.content).strip() if hasattr(resp, "content") else str(resp).strip()
                if content:
                    logger.info("LLM Router succeeded using: DeepSeek")
                    return content
            except Exception as exc:
                errors.append(f"DeepSeek error: {exc}")
                logger.warning("DeepSeek failed: %s", exc)

        raise RuntimeError(f"All LLM providers failed. Errors: {errors}")
