"""Meta Threads Graph API client.

Supports: image container creation, publishing, replies, and token refresh.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

logger = logging.getLogger(__name__)

THREADS_GRAPH_URL = "https://graph.threads.net/v1.0"
THREADS_REFRESH_URL = "https://graph.threads.net/refresh_access_token"
CONTAINER_STATUS_POLL_INTERVAL = 2
CONTAINER_STATUS_MAX_POLLS = 15


@dataclass
class ThreadsClientConfig:
    """Configuration for the Meta Threads Graph API."""

    user_id: str = field(default_factory=lambda: os.getenv("THREADS_USER_ID", ""))
    access_token: str = field(default_factory=lambda: os.getenv("THREADS_ACCESS_TOKEN", ""))
    refresh_token: str = field(default_factory=lambda: os.getenv("THREADS_REFRESH_TOKEN", ""))

    @property
    def is_configured(self) -> bool:
        return bool(self.user_id and self.access_token)


class ThreadsClient:
    """Client for publishing posts and replies to Threads."""

    def __init__(self, config: Optional[ThreadsClientConfig] = None) -> None:
        self.config = config or ThreadsClientConfig()
        self.session = requests.Session()

    # ------------------------------------------------------------------
    # Core: create container
    # ------------------------------------------------------------------
    def create_container(
        self,
        *,
        media_type: str,
        text: str,
        image_url: Optional[str] = None,
        reply_to_id: Optional[str] = None,
    ) -> str:
        """Create a Threads container and return its creation_id."""
        if not self.config.is_configured:
            raise RuntimeError("Threads client is not configured (missing THREADS_USER_ID / THREADS_ACCESS_TOKEN).")

        params: dict[str, str] = {
            "media_type": media_type,
            "access_token": self.config.access_token,
        }
        if text:
            params["text"] = text
        if image_url:
            params["image_url"] = image_url
        if reply_to_id:
            params["reply_to_id"] = reply_to_id

        url = f"{THREADS_GRAPH_URL}/{self.config.user_id}/threads"
        logger.info("Creating Threads container (type=%s, reply_to=%s)", media_type, reply_to_id)
        resp = self.session.post(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        creation_id = data.get("id")
        if not creation_id:
            raise RuntimeError(f"Threads create container returned no id: {data}")
        return str(creation_id)

    # ------------------------------------------------------------------
    # Core: poll container status
    # ------------------------------------------------------------------
    def wait_for_container(self, creation_id: str, max_polls: int = CONTAINER_STATUS_MAX_POLLS) -> bool:
        """Poll the container until it is FINISHED (or FAILED). Returns True when finished."""
        for _ in range(max_polls):
            url = f"{THREADS_GRAPH_URL}/{creation_id}"
            params = {
                "fields": "status,status_code",
                "access_token": self.config.access_token,
            }
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status", "")
            if status == "FINISHED":
                return True
            if status == "ERROR":
                raise RuntimeError(f"Threads container failed: {data}")
            logger.info("Container %s status: %s", creation_id, status)
            time.sleep(CONTAINER_STATUS_POLL_INTERVAL)
        raise TimeoutError(f"Container {creation_id} did not finish in {max_polls} polls.")

    # ------------------------------------------------------------------
    # Core: publish container
    # ------------------------------------------------------------------
    def publish_container(self, creation_id: str) -> str:
        """Publish a container and return the published post ID."""
        url = f"{THREADS_GRAPH_URL}/{self.config.user_id}/threads_publish"
        params = {
            "creation_id": creation_id,
            "access_token": self.config.access_token,
        }
        logger.info("Publishing Threads container %s", creation_id)
        resp = self.session.post(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        post_id = data.get("id")
        if not post_id:
            raise RuntimeError(f"Threads publish returned no id: {data}")
        return str(post_id)

    # ------------------------------------------------------------------
    # High-level: post image + reply
    # ------------------------------------------------------------------
    def post_with_reply(self, image_url: str, main_text: str, reply_text: str) -> tuple[str, str]:
        """Publish an image post with a text reply.

        Returns (published_post_id, reply_post_id).
        """
        creation_id = self.create_container(media_type="IMAGE", text=main_text, image_url=image_url)
        self.wait_for_container(creation_id)
        post_id = self.publish_container(creation_id)
        logger.info("Published Threads post: %s", post_id)

        reply_creation_id = self.create_container(
            media_type="TEXT",
            text=reply_text,
            reply_to_id=post_id,
        )
        self.wait_for_container(reply_creation_id)
        reply_id = self.publish_container(reply_creation_id)
        logger.info("Published Threads reply: %s", reply_id)

        return post_id, reply_id

    # ------------------------------------------------------------------
    # Token refresh (called by refresh_token workflow)
    # ------------------------------------------------------------------
    @staticmethod
    def refresh_access_token(access_token: str) -> str:
        """Exchange a long-lived token for a fresh 60-day token."""
        params = {
            "grant_type": "th_refresh_token",
            "access_token": access_token,
        }
        logger.info("Refreshing Threads access token")
        resp = requests.get(THREADS_REFRESH_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        new_token = data.get("access_token")
        if not new_token:
            raise RuntimeError(f"Threads token refresh returned no token: {data}")
        return str(new_token)
