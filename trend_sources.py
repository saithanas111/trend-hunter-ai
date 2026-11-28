"""Fail-closed parsing for public Instagram product-trend evidence."""
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import re

IGNIX_PRODUCTS_URL = "https://ignix.social/trends/instagram/products"
INSTAGRAM_POST_RE = re.compile(
    r"https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/[A-Za-z0-9_-]+/?",
    re.IGNORECASE,
)


def qualifies_instagram_product_signal(signal):
    """Only a direct Instagram product Reel beating its creator's usual performance qualifies."""
    if not isinstance(signal, dict):
        return False
    if signal.get("source") != "Instagram public product Reel via Ignix tracker":
        return False
    url = str(signal.get("url") or "").strip()
    if not INSTAGRAM_POST_RE.fullmatch(url):
        return False
    if not str(signal.get("title") or "").strip():
        return False
    if not str(signal.get("username") or "").strip():
        return False
    if not str(signal.get("trend_tracker_url") or "").startswith((
        "https://ignix.social/trends/instagram/products",
        "https://ignix.social/trends/products",  # legacy historical tracker route
    )):
        return False

    metric = str(signal.get("trend_metric") or "")
    if not re.search(r"\bviews\b", metric, re.IGNORECASE):
        return False
    ratio = signal.get("creator_usual_ratio")
    if not isinstance(ratio, (int, float)):
        match = re.search(
            r"([0-9]+(?:\.[0-9]+)?)\s*[×x]\s*creator\s+usual",
            metric,
            re.IGNORECASE,
        )
        if not match:
            return False
        ratio = float(match.group(1))
    return float(ratio) > 1.0


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _visible_text(fragment):
    parser = _VisibleText()
    parser.feed(fragment)
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def _relative_performance(text, username):
    """Return a creator-specific x-usual ratio; missing evidence fails closed."""
    matches = re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*[×x]\s*usual", text, re.IGNORECASE)
    if len(matches) == 1:
        return float(matches[0])
    if username:
        summary = re.search(
            r"(?:furthest|most)\s+above\s+usual\s*@"
            + re.escape(username)
            + r"\s*([0-9]+(?:\.[0-9]+)?)\s*[×x]\s*usual",
            text,
            re.IGNORECASE,
        )
        if summary:
            return float(summary.group(1))
    return None


def extract_ignix_instagram_product_signals(page_html, observed_at=None):
    """Accept direct Instagram posts with a product list or explicit product caption, views and >1x usual."""
    raw = unescape(str(page_html or "")).replace("\\/", "/").replace("\\u002F", "/")
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
            r"Products:\s*(.{1,800}?)(?:\s+#|$)", context_text, re.IGNORECASE
        )
        views_match = re.search(r"([\d,.]+\s*[KMB]?)\s+views", context_text, re.IGNORECASE)
        creator_match = re.search(
            r"@([A-Za-z0-9._]+)\s*[·•]\s*([\d,.]+\s*[KMB]?)\s+followers",
            context_text,
            re.IGNORECASE,
        )
        if not views_match or not creator_match:
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

        if products_match:
            product_list = re.sub(r"\s+", " ", products_match.group(1)).strip(" .;")
        else:
            # Current weekly cards may describe the product in the visible Reel caption
            # rather than a separate "Products:" list. Require a concrete product noun.
            creator_text = (
                r"@" + re.escape(creator_match.group(1))
                + r"\s*[·•]\s*" + re.escape(creator_match.group(2))
                + r"\s+followers"
            )
            creator_position = re.search(creator_text, context_text, re.IGNORECASE)
            if not creator_position:
                continue
            caption = context_text[views_match.end():creator_position.start()]
            caption = re.sub(r"^\s+\d{1,2}:\d{2}\s*", " ", caption)
            caption = caption.split("#", 1)[0]
            caption = re.sub(r"\s+", " ", caption).strip(" .;")
            if not re.search(
                r"\b(?:mat|toaster|pen|nails|train|iron|lock|lights|tiles|gadget|organizer|organiser|blender|camera|charger|cable|earbuds|headphones|power bank|lamp|vacuum)\b",
                caption,
                re.IGNORECASE,
            ):
                continue
            product_list = caption
        views = re.sub(r"\s+", "", views_match.group(1)).upper()
        followers = re.sub(r"\s+", "", creator_match.group(2)).upper()
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
            "creator_usual_ratio": ratio,
        })
    return out
