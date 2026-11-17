"""LangGraph StateGraph wiring for the posting pipeline."""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from src.state import AgentState
from src.nodes import (
    copywriter_node,
    guardrail_node,
    history_logger_node,
    idea_generator_node,
    route_after_guardrail,
    shopee_fetcher_node,
    threads_publisher_node,
)

logger = logging.getLogger(__name__)


def build_graph():
    """Construct and compile the LangGraph pipeline."""
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("idea_generator", idea_generator_node)
    workflow.add_node("shopee_fetcher", shopee_fetcher_node)
    workflow.add_node("copywriter", copywriter_node)
    workflow.add_node("guardrail", guardrail_node)
    workflow.add_node("threads_publisher", threads_publisher_node)
    workflow.add_node("history_logger", history_logger_node)

    # Linear flow: idea -> fetch -> copy -> guardrail
    workflow.set_entry_point("idea_generator")
    workflow.add_edge("idea_generator", "shopee_fetcher")
    workflow.add_edge("shopee_fetcher", "copywriter")
    workflow.add_edge("copywriter", "guardrail")

    # Conditional edge: guardrail -> copywriter (retry) or threads_publisher
    workflow.add_conditional_edges(
        "guardrail",
        route_after_guardrail,
        {
            "copywriter": "copywriter",
            "threads_publisher": "threads_publisher",
        },
    )

    # Linear flow: publish -> history -> end
    workflow.add_edge("threads_publisher", "history_logger")
    workflow.add_edge("history_logger", END)

    return workflow.compile()


# Compiled graph singleton
app = build_graph()
