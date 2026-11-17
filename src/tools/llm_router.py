"""Multi-provider Free LLM Router.

Mirrors FreeLLMAPI's routing strategy: tries multiple free LLM providers in sequence
(Gemini -> Groq -> DeepSeek -> OpenAI-compatible custom endpoint) until one succeeds.
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
        """Invoke LLM with automatic fallback across available providers."""
        errors: list[str] = []

        # 1. Try Google Gemini (langchain-google-genai)
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if gemini_key:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI

                llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", api_key=gemini_key)
                resp = llm.invoke(prompt)
                content = str(resp.content).strip() if hasattr(resp, "content") else str(resp).strip()
                if content:
                    logger.info("LLM Router succeeded using: Google Gemini (gemini-2.5-flash)")
                    return content
            except Exception as exc:
                errors.append(f"Gemini error: {exc}")
                logger.warning("Gemini failed, trying next provider: %s", exc)

        # 2. Try Groq (OpenAI-compatible)
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
                    logger.info("LLM Router succeeded using: Groq (llama-3.3-70b-versatile)")
                    return content
            except Exception as exc:
                errors.append(f"Groq error: {exc}")
                logger.warning("Groq failed, trying next provider: %s", exc)

        # 3. Try DeepSeek (OpenAI-compatible)
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
                logger.warning("DeepSeek failed, trying next provider: %s", exc)

        # 4. Try custom OpenAI-compatible endpoint (e.g. local FreeLLMAPI when running locally)
        custom_base = os.getenv("LLM_BASE_URL", "")
        custom_key = os.getenv("LLM_API_KEY", "")
        if custom_base and custom_key:
            try:
                from langchain_openai import ChatOpenAI

                llm = ChatOpenAI(
                    model=os.getenv("LLM_MODEL", "auto"),
                    api_key=custom_key,
                    base_url=custom_base,
                )
                resp = llm.invoke(prompt)
                content = str(resp.content).strip() if hasattr(resp, "content") else str(resp).strip()
                if content:
                    logger.info("LLM Router succeeded using Custom Endpoint: %s", custom_base)
                    return content
            except Exception as exc:
                errors.append(f"Custom endpoint error: {exc}")
                logger.warning("Custom endpoint failed: %s", exc)

        raise RuntimeError(f"All LLM providers failed. Errors: {errors}")
