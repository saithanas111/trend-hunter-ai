"""Fail-closed parsing for public Instagram product-trend evidence."""
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import re

IGNIX_PRODUCTS_URL = "https://ignix.social/trends/products"
INSTAGRAM_POST_RE = re.compile(
    r"https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/[A-Za-z0-9_-]+/?",
    re.IGNORECASE,
)


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def extract_ignix_instagram_product_signals(page_html, observed_at=None):
    """Accept only a direct public Reel URL near a product list and view metric."""
    raw = unescape(str(page_html or "")).replace("\\/", "/").replace("\\u002F", "/")
    parser = _VisibleText()
    parser.feed(raw)
    visible = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()

    start = re.search(r"Rising on Instagram", visible, re.IGNORECASE)
    if not start:
        return []
    tail = visible[start.end():]
    end = re.search(r"What counts as a trend here", tail, re.IGNORECASE)
    section = tail[:end.start()] if end else tail

    products_match = re.search(r"Products:\s*(.{1,800}?)(?:\s+#|$)", section, re.IGNORECASE)
    views_match = re.search(r"([\d,.]+\s*[KMB]?)\s+views", section, re.IGNORECASE)
    if not products_match or not views_match:
        return []

    product_list = re.sub(r"\s+", " ", products_match.group(1)).strip(" .;")
    views = re.sub(r"\s+", "", views_match.group(1)).upper()
    creator_match = re.search(
        r"@([A-Za-z0-9._]+)\s*[·•]\s*([\d,.]+\s*[KMB]?)\s+followers",
        section,
        re.IGNORECASE,
    )
    username = creator_match.group(1) if creator_match else ""
    followers = re.sub(r"\s+", "", creator_match.group(2)).upper() if creator_match else ""

    links = []
    for match in INSTAGRAM_POST_RE.finditer(raw):
        context = raw[max(0, match.start() - 3500): min(len(raw), match.end() + 3500)]
        context_text = re.sub(r"<[^>]+>", " ", unescape(context))
        context_text = re.sub(r"\s+", " ", context_text)
        if (
            re.search(r"Rising on Instagram", context_text, re.IGNORECASE)
            and re.search(r"Products:", context_text, re.IGNORECASE)
            and re.search(r"views", context_text, re.IGNORECASE)
        ):
            url = match.group(0).rstrip("/")
            if url not in links:
                links.append(url)

    if not links:
        return []

    observed = observed_at or datetime.now(timezone.utc).isoformat()
    metric = f"{views} views in the current weekly Instagram product-trend snapshot"
    if followers:
        metric += f"; creator followers {followers}"

    return [{
        "title": f"Instagram product Reel featuring: {product_list}",
        "community": "Instagram public product trends",
        "score": None,
        "comments": None,
        "views": views,
        "username": username,
        "timestamp": observed,
        "url": url,
        "source": "Instagram public product Reel via Ignix tracker",
        "trend_tracker_url": IGNIX_PRODUCTS_URL,
        "trend_metric": metric,
    } for url in links]
