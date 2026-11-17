"""Entry point for the Shopee Affiliate to Threads posting agent.

Usage:
    python main.py            # Full pipeline (publishes to Threads + logs history)
    python main.py --dry-run  # Runs idea->fetch->copy->guardrail and prints output
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("posting-agent")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Shopee Affiliate to Threads posting agent")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute the pipeline without publishing to Threads or modifying history.",
    )
    return parser.parse_args(argv)


def run_pipeline(dry_run: bool) -> int:
    from src.graph import app

    initial_state = {"dry_run": dry_run, "retry_count": 0}
    logger.info("Starting pipeline (dry_run=%s)", dry_run)

    final_state = app.invoke(initial_state)

    if dry_run:
        print("\n" + "=" * 60)
        print("DRY-RUN OUTPUT (not published to Threads)")
        print("=" * 60)
        print(f"Niche:        {final_state.get('niche', '')}")
        print(f"Product:      {final_state.get('product_name', '')}")
        print(f"Item ID:      {final_state.get('item_id', '')}")
        print(f"Price:        RM {final_state.get('price', 0):.2f}")
        print(f"Rating:       {final_state.get('rating', 0):.1f}")
        print(f"Image URL:    {final_state.get('image_url', '')}")
        print(f"Offer Link:   {final_state.get('offer_link', '')}")
        print(f"Source:       {final_state.get('source', '')}")
        print(f"Guardrail:    {final_state.get('guardrail_passed', False)}")
        if final_state.get("guardrail_failures"):
            print(f"  Failures:   {final_state.get('guardrail_failures')}")
        print("-" * 60)
        print("MAIN POST:")
        print(final_state.get("main_post_text", ""))
        print("-" * 60)
        print("REPLY POST:")
        print(final_state.get("reply_post_text", ""))
        print("=" * 60)
        return 0

    # Production path
    if final_state.get("publish_error"):
        logger.error("Pipeline failed during Threads publish: %s", final_state["publish_error"])
        return 1

    if not final_state.get("threads_post_id"):
        logger.error("Pipeline finished without a published post ID.")
        return 1

    logger.info(
        "Published post %s (reply %s) for item %s",
        final_state["threads_post_id"],
        final_state["threads_reply_id"],
        final_state.get("item_id", ""),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run_pipeline(args.dry_run)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline crashed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
