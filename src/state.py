"""LangGraph state definition for the Shopee Affiliate to Threads posting agent."""

from typing import Annotated, Optional, TypedDict

from langgraph.graph import add_messages


class AgentState(TypedDict, total=False):
    """State shared across all LangGraph nodes in the posting pipeline."""

    # --- Input / control ---
    dry_run: bool
    run_id: str
    retry_count: int

    # --- idea_generator_node outputs ---
    niche: str
    niche_reason: str

    # --- shopee_fetcher_node outputs ---
    item_id: str
    product_name: str
    price: float
    image_url: str
    offer_link: str
    rating: float
    commission_rate: float
    source: str  # "shopee_open_api" or "tavily_fallback"

    # --- copywriter_node outputs ---
    main_post_text: str
    reply_post_text: str

    # --- guardrail_node outputs ---
    guardrail_passed: bool
    guardrail_failures: list[str]

    # --- threads_publisher_node outputs ---
    threads_post_id: str
    threads_reply_id: str
    publish_error: Optional[str]

    # --- history_logger_node outputs ---
    history_written: bool

    # --- shared reducer for messages (if any) ---
    messages: Annotated[list, add_messages]