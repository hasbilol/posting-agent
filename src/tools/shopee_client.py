"""Shopee Affiliate product client.

Primary method: Shopee Affiliate Open API (signed GraphQL queries).
Fallback method: Tavily Search API scraping public Shopee MY listings.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

logger = logging.getLogger(__name__)

SHOPEE_GRAPHQL_URL = "https://openapi.affiliate.shopee.com.my/graphql"
SHOPEE_API_VERSION = "2.0"


@dataclass
class ShopeeProduct:
    """Normalized Shopee product result."""

    item_id: str
    product_name: str
    price: float
    image_url: str
    offer_link: str
    rating: float = 0.0
    commission_rate: float = 0.0
    source: str = "shopee_open_api"


@dataclass
class ShopeeClientConfig:
    """Configuration for Shopee Open API requests."""

    app_id: str = field(default_factory=lambda: os.getenv("SHOPEE_APP_ID", ""))
    app_secret: str = field(default_factory=lambda: os.getenv("SHOPEE_APP_SECRET", ""))
    affiliate_link_template: str = field(
        default_factory=lambda: os.getenv(
            "AFFILIATE_LINK_TEMPLATE",
            "https://shopee.com.my/product/affiliate/{item_id}",
        )
    )

    @property
    def is_configured(self) -> bool:
        """True when both Shopee credentials are present."""
        return bool(self.app_id and self.app_secret)


def _sign(app_secret: str, raw_body: str) -> str:
    """Create the SHA256 HMAC signature required by Shopee Open API."""
    signature = hmac.new(
        app_secret.encode("utf-8"),
        raw_body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return signature


def _build_headers(app_id: str, signature: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-SHOPEE-APP-ID": app_id,
        "X-SHOPEE-SIGNATURE": signature,
        "Accept": "application/json",
    }


def _build_raw_body(app_id: str, api_path: str, payload: dict) -> str:
    """Compose the raw body string that gets signed and sent."""
    body = {
        "query": payload.get("query", ""),
        "variables": payload.get("variables", {}),
    }
    return json.dumps(
        {"operationName": "ProductOfferV2", "variables": body["variables"], "query": body["query"]},
        separators=(",", ":"),
    )


class ShopeeAffiliateClient:
    """Client for the Shopee Affiliate Open API (GraphQL) with Tavily fallback."""

    def __init__(
        self,
        config: Optional[ShopeeClientConfig] = None,
        tavily_client: Optional[object] = None,
    ) -> None:
        self.config = config or ShopeeClientConfig()
        self.tavily_client = tavily_client

    def fetch_product(
        self,
        niche: str,
        exclude_item_ids: Optional[set[str]] = None,
        max_rating: float = 4.8,
    ) -> Optional[ShopeeProduct]:
        """Fetch a high-converting product for a niche.

        Tries the Shopee Open API first, then falls back to Tavily.
        """
        exclude_item_ids = exclude_item_ids or set()

        if self.config.is_configured:
            product = self._fetch_via_open_api(niche, exclude_item_ids, max_rating)
            if product:
                return product
            logger.warning("Shopee Open API returned no product; falling back to Tavily.")

        return self._fetch_via_tavily(niche, exclude_item_ids)

    # ------------------------------------------------------------------
    # Primary: Shopee Open API (GraphQL)
    # ------------------------------------------------------------------
    def _fetch_via_open_api(
        self,
        niche: str,
        exclude_item_ids: set[str],
        max_rating: float,
    ) -> Optional[ShopeeProduct]:
        query = """
        query ProductOfferV2($keyword: String!, $limit: Int) {
          productOfferV2(keyword: $keyword, limit: $limit) {
            nodes {
              itemId
              productName
              price
              imageUrl
              rating
              commissionRate
              offerLink
            }
          }
        }
        """
        variables = {"keyword": niche, "limit": 10}
        raw_body = _build_raw_body(self.config.app_id, "productOfferV2", {"query": query, "variables": variables})
        signature = _sign(self.config.app_secret, raw_body)
        headers = _build_headers(self.config.app_id, signature)

        try:
            resp = requests.post(
                SHOPEE_GRAPHQL_URL,
                data=raw_body.encode("utf-8"),
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.error("Shopee Open API request failed: %s", exc)
            return None

        nodes = data.get("data", {}).get("productOfferV2", {}).get("nodes", [])
        for node in nodes:
            item_id = str(node.get("itemId", ""))
            rating = float(node.get("rating", 0) or 0)
            commission_rate = float(node.get("commissionRate", 0) or 0)
            image_url = node.get("imageUrl", "")

            if not item_id or item_id in exclude_item_ids:
                continue
            if rating < max_rating:
                continue
            if not image_url:
                continue

            return ShopeeProduct(
                item_id=item_id,
                product_name=node.get("productName", ""),
                price=float(node.get("price", 0) or 0),
                image_url=image_url,
                offer_link=node.get("offerLink", ""),
                rating=rating,
                commission_rate=commission_rate,
                source="shopee_open_api",
            )

        return None

    # ------------------------------------------------------------------
    # Fallback: Tavily Search API
    # ------------------------------------------------------------------
    def _fetch_via_tavily(self, niche: str, exclude_item_ids: set[str]) -> Optional[ShopeeProduct]:
        if not self.tavily_client:
            api_key = os.getenv("TAVILY_API_KEY", "")
            if not api_key:
                logger.error("No Shopee credentials and no Tavily API key configured.")
                return None
            from tavily import TavilyClient

            self.tavily_client = TavilyClient(api_key=api_key)

        query = f"site:shopee.com.my {niche}"
        try:
            response = self.tavily_client.search(
                query=query,
                search_depth="basic",
                max_results=10,
                include_answer=False,
                include_raw_content=False,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Tavily search failed: %s", exc)
            return None

        results = response.get("results", []) if isinstance(response, dict) else []
        for result in results:
            url = result.get("url", "")
            title = result.get("title", "")
            item_id = self._extract_item_id(url)
            if not item_id or item_id in exclude_item_ids:
                continue

            offer_link = self.config.affiliate_link_template.format(item_id=item_id)
            return ShopeeProduct(
                item_id=item_id,
                product_name=title or niche,
                price=0.0,
                image_url="",
                offer_link=offer_link,
                rating=0.0,
                commission_rate=0.0,
                source="tavily_fallback",
            )

        return None

    @staticmethod
    def _extract_item_id(url: str) -> str:
        """Extract Shopee item ID from a product URL.

        Shopee MY URLs look like: https://shopee.com.my/Product-Name-i.1234.567890123
        or https://shopee.com.my/product/567890123
        """
        if not url:
            return ""
        parts = url.rstrip("/").split("/")
        for part in reversed(parts):
            if part.isdigit():
                return part
        # Also check query params (?iItemId=...)
        import urllib.parse

        parsed = urllib.parse.urlparse(url)
        for key in ("iItemId", "itemId", "sp_atk"):
            val = urllib.parse.parse_qs(parsed.query).get(key)
            if val and val[0].isdigit():
                return val[0]
        return ""
