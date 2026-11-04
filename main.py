import os
import re
import json
import time
import html
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urljoin
from datetime import datetime, timezone

from google import genai

API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY) if API_KEY else None
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TrendHunterAI/1.0; +https://github.com/saithanas111/trend-hunter-ai)"}
TRENDS_URL = "https://trends.google.com/trending/rss?geo=PK"
REDDIT_FEEDS = [
    "https://www.reddit.com/r/BuyItForLife/hot.json?limit=20",
    "https://www.reddit.com/r/gadgets/hot.json?limit=20",
    "https://www.reddit.com/r/DidntKnowIWantedThat/hot.json?limit=20",
]

def fetch_url(url, timeout=18):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()

def fetch_google_trends():
    try:
        root = ET.fromstring(fetch_url(TRENDS_URL))
        rows = []
        for item in root.findall(".//item")[:20]:
            title = (item.findtext("title") or "").strip()
            traffic = (item.findtext("ht:approx_traffic", default="", namespaces={"ht": "https://trends.google.com/trending/rss"}) or "").strip()
            if title:
                rows.append({"topic": title, "approx_traffic": traffic or None, "source": "Google Trends Pakistan RSS"})
        return rows, None
    except Exception as exc:
        return [], str(exc)[:200]

def fetch_social_signals():
    rows, errors = [], []
    for feed in REDDIT_FEEDS:
        try:
            data = json.loads(fetch_url(feed).decode("utf-8"))
            for child in data.get("data", {}).get("children", []):
                post = child.get("data", {})
                title = (post.get("title") or "").strip()
                if title and not post.get("stickied"):
                    rows.append({
                        "title": title[:220],
                        "community": post.get("subreddit"),
                        "score": post.get("score"),
                        "comments": post.get("num_comments"),
                        "url": "https://www.reddit.com" + (post.get("permalink") or ""),
                        "source": "Reddit public hot posts",
                    })
        except Exception as exc:
            errors.append(str(exc)[:140])
    rows.sort(key=lambda x: (x.get("score") or 0) + 2 * (x.get("comments") or 0), reverse=True)
    return rows[:30], errors

class DarazProductParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self.current = None
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        href = attrs.get("href", "")
        if tag == "a" and "/products/" in href and not self.current:
            if href.startswith("//"):
                href = "https:" + href
            elif href.startswith("/"):
                href = "https://www.daraz.pk" + href
            if "daraz.pk" in href:
                self.current = {"url": href.split("?")[0], "text": ""}
                self.depth = 1
        elif self.current:
            self.depth += 1

    def handle_data(self, data):
        if self.current:
            self.current["text"] += " " + data.strip()

    def handle_endtag(self, tag):
        if self.current:
            self.depth -= 1
            if self.depth <= 0:
                title = re.sub(r"\s+", " ", html.unescape(self.current["text"])).strip()
                if len(title) > 12:
                    self.current["title"] = title[:240]
                    self.items.append(self.current)
                self.current = None
                self.depth = 0

def search_daraz(query, limit=4):
    url = "https://www.daraz.pk/catalog/?q=" + urllib.parse.quote(query)
    try:
        raw = fetch_url(url, timeout=22).decode("utf-8", errors="ignore")
        parser = DarazProductParser()
        parser.feed(raw)
        seen, found = set(), []
        for item in parser.items:
            if item["url"] not in seen:
                seen.add(item["url"])
                found.append({
                    "title": item["title"],
                    "url": item["url"],
                    "search_query": query,
                    "source": "Daraz Pakistan search page",
                    "verification": "Listing URL and title extracted from live Daraz search HTML; seller, price, stock, reviews and affiliate eligibility not verified."
                })
            if len(found) >= limit:
                break
        return found, None
    except Exception as exc:
        return [], str(exc)[:200]


def upload_product_image_to_cloudinary(product_url):
    """Fetch the listing's public Open Graph image and store it in Cloudinary."""
    if not all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
        return None, "Cloudinary credentials are not configured."
    try:
        page = fetch_url(product_url, timeout=22).decode("utf-8", errors="ignore")
        image = re.search(r"<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)", page, re.I)
        if not image:
        image = re.search(r"<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)", page, re.I)
        if not image:
            return None, "No public og:image found on the listing page."
        image_url = urljoin(product_url, html.unescape(image.group(1)))
        import cloudinary
        import cloudinary.uploader
        cloudinary.config(
            cloud_name=CLOUDINARY_CLOUD_NAME,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET,
            secure=True,
        )
        result = cloudinary.uploader.upload(
            image_url,
            folder="trend-hunter/products",
            resource_type="image",
        )
        return result.get("secure_url"), None
    except Exception as exc:
        return None, str(exc)[:200]

def gemini_text(prompt):
    if not client:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    last = None
    for attempt in range(4):
        try:
            response = client.models.generate_content(model=MODEL, contents=prompt)
            if response.text and response.text.strip():
                return response.text.strip()
            last = "Gemini returned an empty response."
        except Exception as exc:
            last = str(exc)[:200]
            if attempt < 2:
                time.sleep(12 * (attempt + 1))
    raise RuntimeError(last or "Gemini request failed.")

def make_queries(trends, social):
    source = {"google_trends": trends[:15], "social_posts": social[:18]}
    prompt = """From these current Pakistan search-interest and public social-discussion signals, extract up to 8 concrete physical product search queries that have a defensible connection to the source posts/topics. Return ONLY valid JSON array of short search queries. Do not invent viral status, demand or products unrelated to the source. If no product connection exists, return []. Signals:
""" + json.dumps(source, ensure_ascii=False)
    text = gemini_text(prompt)
    match = re.search(r"\[[\s\S]*\]", text)
    if not match:
        raise ValueError("Trend-to-product query response was not valid JSON array.")
    values = json.loads(match.group(0))
    return [str(x).strip()[:100] for x in values if str(x).strip()][:8]

def create_social_copy(product):
    prompt = """Create concise original platform-specific marketing copy for this Daraz Pakistan product candidate.
Return ONLY JSON with keys facebook_caption, instagram_caption, tiktok_hook, video_script, hashtags (array of 5).
Do not claim it is viral, best-selling, discounted, tested, or in stock. Do not invent price, features or guarantees.
    prompt = """Create concise original platform-specific marketing copy for this Daraz Pakistan product candidate.
Return ONLY JSON with keys facebook_caption, instagram_caption, tiktok_hook, video_script, hashtags (array of 5).
Do not claim it is viral, best-selling, discounted, tested, or in stock. Do not invent price, features or guarantees.
Product title: """ + product["title"] + "\nDaraz listing: " + product["url"]
    raw = gemini_text(prompt)
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        raise ValueError("Social copy response was not valid JSON.")
    data = json.loads(match.group(0))
    required = ["facebook_caption", "instagram_caption", "tiktok_hook", "video_script", "hashtags"]
    if any(not data.get(k) for k in required):
        raise ValueError("Social copy response is missing required fields.")
    return data

def build_report(trends, social, products, errors):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Trend Hunter AI Report", "",
        f"**Generated:** {stamp}", "",
        "## Live research status",
        f"- Google Trends Pakistan topics fetched: {len(trends)}",
        f"- Public Reddit hot-post signals fetched: {len(social)}",
        f"- Daraz listing candidates extracted: {len(products)}",
        "- Reddit scores/comments and Google Trends are attention/search signals, not proof of Pakistan sales.",
        "- Daraz candidates are live search-page extracts only; seller quality, price, stock, reviews, shipping, returns and affiliate eligibility still require verification.",
        "- No affiliate links are generated by this run. The known Daraz method is manual and no official affiliate-link API has been confirmed.",
        f"- Product images uploaded to Cloudinary: {sum(1 for p in products if p.get(chr(112)+chr(117)+chr(98)+chr(108)+chr(105)+chr(99)+chr(95)+chr(105)+chr(109)+chr(97)+chr(103)+chr(101)+chr(95)+chr(117)+chr(114)+chr(108))) }",
        "- No social posts are published by this run.", ""
    ]
    if trends:
        lines += ["## Google Trends Pakistan signals"]
        lines += [f"- {x['topic']} (approx. traffic: {x['approx_traffic'] or 'not provided'})" for x in trends[:12]]
        lines.append("")
    if social:
        lines += ["## Public social discussion signals"]
        lines += [f"- [{x['community']}] {x['title']} (score {x['score']}, comments {x['comments']}) — {x['url']}" for x in social[:12]]
        lines.append("")
    if products:
        lines += ["## Daraz Pakistan listing candidates"]
        for i, p in enumerate(products, 1):
            lines += [
                f"### Candidate {i}: {p['title']}",
                f"- Search query: {p['search_query']}",
    prompt = """Create concise original platform-specific marketing copy for this Daraz Pakistan product candidate.
Return ONLY JSON with keys facebook_caption, instagram_caption, tiktok_hook, video_script, hashtags (array of 5).
Do not claim it is viral, best-selling, discounted, tested, or in stock. Do not invent price, features or guarantees.
Product title: """ + product["title"] + "\nDaraz listing: " + product["url"]
                f"- Status: {p['verification']}", ""
            ]
    else:
        lines += [
            "## Daraz matching result",
            "No Daraz product listing could be reliably extracted in this run. No product has been labelled as matched or verified, and no generic product ideas have been substituted.", ""
        ]
    lines += ["## Errors / limitations"]
    lines += [f"- {e}" for e in errors] if errors else ["- No fetch errors recorded."]
    lines += [
        "", "## Next required verification",
        "Open a candidate listing and verify seller rating/history, current price, reviews, sold count if shown, stock, shipping, returns and affiliate eligibility. Affiliate deeplink generation remains manual until Daraz provides a supported automation route."
    ]
    return "\n".join(lines) + "\n"

def main():
    errors = []
    trends, err = fetch_google_trends()
    if err: errors.append("Google Trends: " + err)
    social, social_errors = fetch_social_signals()
    errors += ["Social feed: " + x for x in social_errors[:3]]
    products = []
    try:
        queries = make_queries(trends, social)
        if not queries:
            errors.append("No defensible product queries could be derived from current trend signals.")
        for query in queries:
            matches, search_error = search_daraz(query)
            if search_error:
                errors.append(f"Daraz search for '{query}': {search_error}")
            products.extend(matches)
            if len(products) >= 15:
                break
            time.sleep(2)
    except Exception as exc:
        errors.append("AI trend-to-product matching: " + str(exc)[:200])
    unique = {}
    for item in products:
        unique.setdefault(item["url"], item)
    products = list(unique.values())[:15]
    for product in products:
        try:
            product["social_copy"] = create_social_copy(product)
            image_url, image_error = upload_product_image_to_cloudinary(product["url"])
            product["public_image_url"] = image_url or ""
            if image_error:
                product["image_upload_error"] = image_error
        except Exception as exc:
            product["social_copy_error"] = str(exc)[:200]
            errors.append("Social copy for '" + product["title"][:80] + "': " + str(exc)[:160])
        time.sleep(1)
    report = build_report(trends, social, products, errors)
    with open("trend_report.md", "w", encoding="utf-8") as f:
        f.write(report)
    with open("daraz_candidates.json", "w", encoding="utf-8") as f:
        json.dump({"generated_at": datetime.now(timezone.utc).isoformat(), "count": len(products), "items": products}, f, ensure_ascii=False, indent=2)
    print(report)
    print(f"Saved {len(products)} Daraz listing candidates.")

if __name__ == "__main__":
    main()
