"""Fail-closed parsing for public Instagram product-trend evidence."""
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import re

IGNIX_PRODUCTS_URL = "https://ignix.social/trends/products"
INSTAGRAM_POST_RE = re.compile(
    r"https?://(?:www\\.)?instagram\\.com/(?:p|reel|tv)/[A-Za-z0-9_-]+/?",
    re.IGNORECASE,
)


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _visible_text(fragment):
    parser = _VisibleText()
    parser.feed(fragment)
    return re.sub(r"\\s+", " ", " ".join(parser.parts)).strip()


def _relative_performance(text, username):
    """Return a creator-specific x-usual ratio; missing evidence fails closed."""
    matches = re.findall(r"([0-9]+(?:\\.[0-9]+)?)\\s*[×x]\\s*usual", text, re.IGNORECASE)
    if len(matches) == 1:
        return float(matches[0])
    if username:
        summary = re.search(
            r"(?:furthest|most)\\s+above\\s+usual\\s*@"
            + re.escape(username)
            + r"\\s*([0-9]+(?:\\.[0-9]+)?)\\s*[×x]\\s*usual",
            text,
            re.IGNORECASE,
        )
        if summary:
            return float(summary.group(1))
    return None


def extract_ignix_instagram_product_signals(page_html, observed_at=None):
    """Accept only direct Instagram posts with a product list, views and >1x usual."""
    raw = unescape(str(page_html or "")).replace("\\\\/", "/").replace("\\\\u002F", "/")
    visible = _visible_text(raw)
    start = re.search(r"Rising on Instagram", visible, re.IGNORECASE)
    if not start:
        return []
    tail = visible[start.end():]
    end = re.search(r"What counts as a trend here", tail, re.IGNORECASE)
    section = tail[:end.start()] if end else tail

    observed = observed_at or datetime.now(timezone.utc).isoformat()
    out = []
    seen = set()

    for match in INSTAGRAM_POST_RE.finditer(raw):
        context = raw[max(0, match.start() - 3500): min(len(raw), match.end() + 3500)]
        context_text = _visible_text(context)
        if not re.search(r"Rising on Instagram", context_text, re.IGNORECASE):
            continue
        products_match = re.search(
            r"Products:\\s*(.{1,800}?)(?:\\s+#|$)", context_text, re.IGNORECASE
        )
        views_match = re.search(r"([\\d,.]+\\s*[KMB]?)\\s+views", context_text, re.IGNORECASE)
        creator_match = re.search(
            r"@([A-Za-z0-9._]+)\\s*[·•]\\s*([\\d,.]+\\s*[KMB]?)\\s+followers",
            context_text,
            re.IGNORECASE,
        )
        if not products_match or not views_match or not creator_match:
            continue

        username = creator_match.group(1)
        ratio = _relative_performance(context_text, username)
        if ratio is None:
            ratio = _relative_performance(section, username)
        if ratio is None or ratio <= 1.0:
            continue

        url = match.group(0).rstrip("/")
        if url in seen:
            continue
        seen.add(url)

        product_list = re.sub(r"\\s+", " ", products_match.group(1)).strip(" .;")
        views = re.sub(r"\\s+", "", views_match.group(1)).upper()
        followers = re.sub(r"\\s+", "", creator_match.group(2)).upper()
        metric = (
            f"{ratio:g}x creator usual; {views} views in the current weekly "
            f"Instagram product-trend snapshot; creator followers {followers}"
        )
        out.append({
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
        })
    return out
