"""LangGraph node implementations for the posting pipeline."""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

import requests

from src.state import AgentState
from src.tools.llm_router import LLMRouter
from src.tools.shopee_client import ShopeeAffiliateClient
from src.tools.threads_client import ThreadsClient

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HISTORY_FILE = PROJECT_ROOT / "data" / "posted_history.json"
MYT = timezone(timedelta(hours=8))

# Fresh, high-demand Shopee MY niches (avoids repeating too often)
NICHE_POOL = [
    "desk setup gadget",
    "home organization",
    "car accessories",
    "motorcycle accessories",
    "daily lifestyle essential",
    "kitchen gadget",
    "pet accessories",
    "smart home device",
    "fitness equipment",
    "phone accessories",
]


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _load_history() -> list[dict[str, Any]]:
    if not HISTORY_FILE.exists():
        return []
    try:
        with HISTORY_FILE.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read history file: %s", exc)
        return []


def _save_history(entries: list[dict[str, Any]]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("w", encoding="utf-8") as fh:
        json.dump(entries, fh, ensure_ascii=False, indent=2)


def _get_router() -> LLMRouter:
    return LLMRouter()


def _image_reachable(url: str) -> bool:
    if not url:
        return False
    try:
        resp = requests.head(url, timeout=10, allow_redirects=True)
        return resp.status_code == 200
    except requests.RequestException:
        return False


# ----------------------------------------------------------------------
# Node 1: idea_generator_node
# ----------------------------------------------------------------------
def idea_generator_node(state: AgentState) -> dict[str, Any]:
    history = _load_history()
    past_niches = [entry.get("niche", "") for entry in history]

    router = _get_router()
    prompt = (
        "Pick ONE Shopee Malaysia niche keyword for a high-converting affiliate product.\n"
        f"Candidate niches: {', '.join(NICHE_POOL)}\n"
        f"Recently used niches (avoid): {', '.join(past_niches[-10:]) or 'none'}\n"
        "Return only the niche keyword, nothing else."
    )
    niche = router.invoke(prompt).strip()

    # Fallback if LLM output looks weird
    if not niche or len(niche) > 60:
        niche = NICHE_POOL[len(past_niches) % len(NICHE_POOL)]

    return {
        "niche": niche,
        "niche_reason": "LLM-selected fresh niche avoiding recent repeats.",
        "run_id": uuid.uuid4().hex,
        "retry_count": state.get("retry_count", 0),
    }


# ----------------------------------------------------------------------
# Node 2: shopee_fetcher_node
# ----------------------------------------------------------------------
def shopee_fetcher_node(state: AgentState) -> dict[str, Any]:
    history = _load_history()
    posted_ids = {str(entry.get("item_id", "")) for entry in history}

    client = ShopeeAffiliateClient()
    product = client.fetch_product(
        niche=state["niche"],
        exclude_item_ids=posted_ids,
        max_rating=4.8,
    )

    if not product:
        raise RuntimeError(f"No product found for niche '{state['niche']}' after filtering posted items.")

    return {
        "item_id": product.item_id,
        "product_name": product.product_name,
        "price": product.price,
        "image_url": product.image_url,
        "offer_link": product.offer_link,
        "rating": product.rating,
        "commission_rate": product.commission_rate,
        "source": product.source,
    }


# ----------------------------------------------------------------------
# Node 3: copywriter_node
# ----------------------------------------------------------------------
def copywriter_node(state: AgentState) -> dict[str, Any]:
    router = _get_router()
    product = state["product_name"]
    price = state.get("price", 0.0)
    niche = state["niche"]

    main_prompt = (
        f"Write a casual Malaysian Threads main post about: '{product}' "
        f"(niche: {niche}, price RM{price:.2f} if available).\n"
        "It must be under 450 characters, no links, no hashtag spam, natural BM/Manglish.\n"
        "Output ONLY the post text."
    )
    main_text = router.invoke(main_prompt).strip()

    offer_link = state.get("offer_link", "")
    reply_text = f"Yang tanya link kat mana, boleh tengok kat sini 👉 {offer_link}"

    # Truncate if LLM overran
    main_text = main_text[:450]
    reply_text = reply_text[:450]

    return {
        "main_post_text": main_text,
        "reply_post_text": reply_text,
    }


# ----------------------------------------------------------------------
# Node 4: guardrail_node (conditional edge)
# ----------------------------------------------------------------------
def guardrail_node(state: AgentState) -> dict[str, Any]:
    failures: list[str] = []
    main_text = state.get("main_post_text", "")
    reply_text = state.get("reply_post_text", "")
    image_url = state.get("image_url", "")
    offer_link = state.get("offer_link", "")

    if not main_text or len(main_text) > 480:
        failures.append("main_post_text invalid (empty or > 480 chars)")
    if not reply_text or len(reply_text) > 480:
        failures.append("reply_post_text invalid (empty or > 480 chars)")
    if not _image_reachable(image_url):
        failures.append("image_url not reachable")
    if not offer_link or not offer_link.startswith("http"):
        failures.append("offer_link invalid")

    return {
        "guardrail_passed": len(failures) == 0,
        "guardrail_failures": failures,
    }


# ----------------------------------------------------------------------
# Node 5: threads_publisher_node
# ----------------------------------------------------------------------
def threads_publisher_node(state: AgentState) -> dict[str, Any]:
    if state.get("dry_run"):
        return {
            "threads_post_id": "DRY-RUN",
            "threads_reply_id": "DRY-RUN",
            "publish_error": None,
        }

    client = ThreadsClient()
    try:
        post_id, reply_id = client.post_with_reply(
            image_url=state["image_url"],
            main_text=state["main_post_text"],
            reply_text=state["reply_post_text"],
        )
        return {
            "threads_post_id": post_id,
            "threads_reply_id": reply_id,
            "publish_error": None,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Threads publish failed: %s", exc)
        return {
            "threads_post_id": "",
            "threads_reply_id": "",
            "publish_error": str(exc),
        }


# ----------------------------------------------------------------------
# Node 6: history_logger_node
# ----------------------------------------------------------------------
def history_logger_node(state: AgentState) -> dict[str, Any]:
    if state.get("dry_run"):
        return {"history_written": False}

    now = datetime.now(MYT)
    entry = {
        "item_id": state.get("item_id", ""),
        "product_name": state.get("product_name", ""),
        "niche": state.get("niche", ""),
        "price": state.get("price", 0.0),
        "image_url": state.get("image_url", ""),
        "offer_link": state.get("offer_link", ""),
        "threads_post_id": state.get("threads_post_id", ""),
        "threads_reply_id": state.get("threads_reply_id", ""),
        "timestamp": now.isoformat(),
    }

    history = _load_history()
    history.append(entry)
    _save_history(history)
    logger.info("Logged post to history: %s", entry["item_id"])
    return {"history_written": True}


# ----------------------------------------------------------------------
# Conditional routing helper (used by graph.py)
# ----------------------------------------------------------------------
def route_after_guardrail(state: AgentState) -> str:
    """Return the next node based on guardrail + retry counter."""
    if state.get("guardrail_passed"):
        return "threads_publisher"
    retries = state.get("retry_count", 0)
    if retries >= 2:
        logger.warning("Guardrail failed 3 times; proceeding with last content.")
        return "threads_publisher"
    return "copywriter"
