import os, re, json, time, html, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urljoin
from datetime import datetime, timezone
from google import genai

API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY) if API_KEY else None
MODELS = [m.strip() for m in os.environ.get("GEMINI_MODELS", os.environ.get("GEMINI_MODEL", "gemini-3.8-flash,gemini-3.7-flash,gemini-3.6-flash")).split(",") if m.strip()]
CLOUDINARY = {k: os.environ.get(k) for k in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")}
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125 Safari/537.36"}
TRENDS_URL = "https://trends.google.com/trending/rss?geo=PK"
TIKTOK_TRENDS_URL = "https://viralcatcher.com/trending/phones-electronics"
REDDIT_FEEDS = [
    "https://www.reddit.com/r/gadgets/hot.json?limit=15",
    "https://www.reddit.com/r/DidntKnowIWantedThat/hot.json?limit=15",
]

def fetch_url(url, timeout=20):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read()

def fetch_google_trends():
    try:
        root = ET.fromstring(fetch_url(TRENDS_URL))
        ns = {"ht": "https://trends.google.com/trending/rss"}
        out = []
        for item in root.findall(".//item")[:20]:
            title = (item.findtext("title") or "").strip()
            traffic = (item.findtext("ht:approx_traffic", default="", namespaces=ns) or "").strip()
            if title:
                out.append({"topic": title, "approx_traffic": traffic or None, "source": "Google Trends Pakistan RSS"})
        return out, None
    except Exception as e:
        return [], str(e)[:200]


def fetch_tiktok_trend_signals():
    """Read public TikTok video trend summaries from a third-party tracker; not Pakistan-specific."""
    try:
        raw = fetch_url(TIKTOK_TRENDS_URL, 25).decode("utf-8", "ignore")
        plain = html.unescape(re.sub(r"<[^>]+>", " ", raw))
        plain = re.sub(r"\s+", " ", plain)
        pattern = re.compile(
            r"Number\s+\d+\s+(.*?)\s+(?:\+[\d,.]+[KMB]\s+views(?:\s+in\s+\d+h)?\s+)?"
            r"([\d,.]+[KMB]\s+total views)\s+(.{1,100}?)\s+Posted\s+([A-Za-z]+\s+\d+)",
            re.I
        )
        out = []
        for match in pattern.finditer(plain):
            title, views, creator, posted = [re.sub(r"\s+", " ", x).strip() for x in match.groups()]
            out.append({"title": title[:260], "total_views": views, "creator": creator[:100],
                        "posted": posted, "source": "ViralCatcher public TikTok trend tracker",
                        "source_url": TIKTOK_TRENDS_URL, "region": "TikTok Shop tracker; not Pakistan-specific"})
        return out[:10], None
    except Exception as e:
        return [], str(e)[:200]

def fetch_social_signals():
    out, errors = [], []
    for url in REDDIT_FEEDS:
        try:
            data = json.loads(fetch_url(url).decode("utf-8"))
            for child in data.get("data", {}).get("children", []):
                p = child.get("data", {})
                if p.get("title") and not p.get("stickied"):
                    out.append({"title": p["title"][:220], "community": p.get("subreddit"),
                                "score": p.get("score"), "comments": p.get("num_comments"),
                                "url": "https://www.reddit.com" + p.get("permalink", ""),
                                "source": "Reddit public hot posts"})
        except Exception as e:
            errors.append(str(e)[:150])
    out.sort(key=lambda x: (x.get("score") or 0) + 2*(x.get("comments") or 0), reverse=True)
    return out[:25], errors

class ProductParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.capture = False
        self.depth = 0
        self.current = None
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        href = a.get("href", "")
        if tag == "a" and "/products/" in href and not self.capture:
            self.current = {"url": href, "title": ""}
            self.capture, self.depth = True, 1
        elif self.capture:
            self.depth += 1
    def handle_data(self, data):
        if self.capture and self.current:
            self.current["title"] += " " + data.strip()
    def handle_endtag(self, tag):
        if self.capture:
            self.depth -= 1
            if self.depth <= 0:
                p = self.current
                p["title"] = re.sub(r"\s+", " ", html.unescape(p["title"])).strip()
                if p["title"]:
                    self.links.append(p)
                self.capture, self.current, self.depth = False, None, 0

def search_daraz(query, limit=4):
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
    special_tags = {
        "mini digital vlogging camera": ["mini-vlogger-camera", "mini-digital-camera-keychain"],
        "mini keychain digital camera": ["mini-digital-camera-keychain", "mini-keychain-cameras"],
        "tiktok scrolling remote control": ["tiktok-scroll-remote", "bluetooth-tiktok-remote-control"],
        "90 degree usb c elbow charging cable": ["usb-c-cable-90-degree", "usb-c-to-c-angled-cable", "90-degree-micro-usb-cable"],
        "fitness tracker silent alarm": ["fitness-tracker", "fitness-band"],
        "5000mah mini power bank": ["mini-power-bank", "power-bank-5000mah"],
    }
    urls = ["https://www.daraz.pk/catalog/?q=" + urllib.parse.quote(query)]
    urls += ["https://www.daraz.pk/tag/" + tag + "/" for tag in special_tags.get(query.lower(), [slug])]
    seen, found = set(), []
    diagnostics = []
    for search_url in urls:
        try:
            raw = fetch_url(search_url, 20).decode("utf-8", "ignore")
            parser = ProductParser()
            parser.feed(raw)
            candidates = list(parser.links)
            normalized = raw.replace("\\/", "/").replace("\\u002F", "/")
            pattern = r'(?:(?:https?:)?//www\.daraz\.pk)?/products/[^"\\<>\s]+?-i\d+(?:-s\d+)?\.html'
            embedded = re.findall(pattern, normalized, flags=re.I)
            candidates += [{"url": u, "title": ""} for u in embedded]
            diagnostics.append(f"{search_url}: {len(raw)} bytes, {len(parser.links)} anchor links, {len(embedded)} embedded URLs")
            for p in candidates:
                link = urljoin("https://www.daraz.pk", html.unescape(p["url"])).split("?")[0]
                if not re.match(r"^https://www\.daraz\.pk/products/.+-i\d+(?:-s\d+)?\.html$", link, re.I) or link in seen:
                    continue
                seen.add(link)
                title = re.sub(r"[-_]+", " ", p.get("title") or "")
                title = re.sub(r"\s+", " ", title).strip() or query
                found.append({"title": title[:240], "url": link, "search_query": query,
                              "source": "Daraz Pakistan public catalog/tag page",
                              "verification": "Listing URL extracted only; seller, price, stock, reviews and affiliate eligibility NOT verified."})
                if len(found) >= limit:
                    return found, None
        except Exception as e:
            diagnostics.append(f"{search_url}: {str(e)[:120]}")
        time.sleep(1)
    if not found:
        return [], "No Daraz product URLs extracted. " + " | ".join(diagnostics)
    return found, None

def available_gemini_models():
    if MODELS:
        return MODELS
    if not client:
        return []
    try:
        available = []
        for model in client.models.list():
            name = getattr(model, "name", "") or ""
            actions = getattr(model, "supported_actions", []) or []
            if name and (not actions or "generateContent" in actions):
                clean = name.removeprefix("models/")
                if "flash" in clean.lower():
                    available.append(clean)
        return available[:12]
    except Exception:
        return ["gemini-3.8-flash"]

def gemini_text(prompt):
    if not client:
        raise RuntimeError("GEMINI_API_KEY is missing.")
    failures = []
    models_to_try = available_gemini_models()
    if not models_to_try:
        raise RuntimeError("No Gemini models supporting generateContent were returned for this API key.")
    for model in models_to_try:
        for attempt in range(2):
            try:
                response = client.models.generate_content(model=model, contents=prompt)
                if response.text and response.text.strip():
                    return response.text.strip()
                failures.append(f"{model}: empty response")
            except Exception as e:
                message = str(e)[:180]
                failures.append(f"{model}: {message}")
                if attempt == 0 and any(code in message.lower() for code in ("503", "429", "unavailable", "high demand", "deadline")):
                    time.sleep(5)
                    continue
                break
    raise RuntimeError("All discovered/configured Gemini models failed: " + " | ".join(failures[-6:]))

def parse_json(text, kind):
    match = re.search(r"\[[\s\S]*\]" if kind == "array" else r"\{[\s\S]*\}", text)
    if not match: raise ValueError("Gemini did not return valid JSON.")
    return json.loads(match.group(0))

def make_queries(trends, social, tiktok):
    # Product-first: build Daraz queries directly from observed TikTok product signals.
    # Do not let unrelated people/news topics from Google Trends displace social product trends.
    if tiktok:
        queries, seen = [], set()
        for signal in tiktok:
            title = signal.get("title", "").lower()
            if "remote control" in title and ("scroll" in title or "tiktok" in title or "page turn" in title):
                query = "TikTok scrolling remote control"
            elif "usb-c" in title or "usb c" in title or ("elbow" in title and "cable" in title):
                query = "90 degree USB C elbow charging cable"
            elif "keychain" in title and "camera" in title:
                query = "mini keychain digital camera"
            elif "camera" in title or "vlogging" in title:
                query = "mini digital vlogging camera"
            elif "fitness tracker" in title:
                query = "fitness tracker silent alarm"
            elif "power bank" in title or "portable charger" in title:
                query = "5000mAh mini power bank"
            elif "dvd player" in title:
                query = "portable DVD player"
            else:
                words = re.findall(r"[a-z0-9]+", title)
                query = " ".join(words[:7])
            key = query.casefold()
            if query and key not in seen:
                seen.add(key)
                queries.append(query)
            if len(queries) >= 8:
                break
        return queries
    # Use Gemini only as a fallback when no public TikTok product trend signal is available.
    prompt = ("From current Pakistan search and public discussion signals, return ONLY a JSON array of up to 8 "
              "physical product search queries clearly connected to the signals. Do not invent trends or demand. "
              "Return [] if no defensible product match. Signals:\\n" +
              json.dumps({"google_trends_pk": trends[:15], "reddit_public_posts": social[:15]}, ensure_ascii=False))
    vals = parse_json(gemini_text(prompt), "array")
    return [str(x).strip()[:100] for x in vals if str(x).strip()][:8]

def create_social_copy(product):
    prompt = ("Write safe, concise copy for this Daraz listing candidate. Return ONLY JSON with keys "
              "facebook_caption, instagram_caption, tiktok_hook, video_script, hashtags (array of 5). "
              "Do not claim viral/best-selling/discounted/tested/in-stock; do not invent price or features.\n"
              + json.dumps({"title": product["title"], "url": product["url"]}, ensure_ascii=False))
    data = parse_json(gemini_text(prompt), "object")
    for key in ("facebook_caption", "instagram_caption", "tiktok_hook", "video_script", "hashtags"):
        if not data.get(key): raise ValueError("Missing copy field: " + key)
    return data

def upload_product_image_to_cloudinary(product_url):
    if not all(CLOUDINARY.values()):
        return None, "Cloudinary credentials missing."
    try:
        page = fetch_url(product_url, 20).decode("utf-8", "ignore")
        m = re.search(r'<meta[^>]+(?:property=["\']og:image["\'][^>]+content=["\']([^"\']+)|content=["\']([^"\']+)["\'][^>]+property=["\']og:image)', page, re.I)
        image = (m.group(1) or m.group(2)) if m else None
        if not image: return None, "No public og:image found."
        import cloudinary, cloudinary.uploader
        cloudinary.config(cloud_name=CLOUDINARY["CLOUDINARY_CLOUD_NAME"],
                          api_key=CLOUDINARY["CLOUDINARY_API_KEY"],
                          api_secret=CLOUDINARY["CLOUDINARY_API_SECRET"], secure=True)
        result = cloudinary.uploader.upload(urljoin(product_url, html.unescape(image)),
                                             folder="trend-hunter/products", resource_type="image")
        return result.get("secure_url"), None
    except Exception as e:
        return None, str(e)[:200]

def build_report(trends, social, tiktok, products, errors, queries_used=None):
    lines = ["# Trend Hunter AI Report", "",
             "**Generated:** " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "",
             "**AI models attempted:** " + ", ".join(MODELS), "",
             "## Live research status",
             f"- Google Trends Pakistan topics fetched: {len(trends)}",
             f"- Public Reddit hot-post signals fetched: {len(social)}",
             f"- Public TikTok trend tracker product signals fetched: {len(tiktok)} (global, not Pakistan-specific)",
             f"- Daraz listing candidates extracted: {len(products)}",
             f"- Product images uploaded to Cloudinary: {sum(bool(p.get('public_image_url')) for p in products)}",
             "- Trend/search signals are not proof of Pakistan sales.",
             "- Daraz listing extraction does not verify seller quality, price, stock, reviews, delivery or affiliate eligibility.",
             "- Affiliate deeplinks are not generated; no supported Daraz affiliate API has been confirmed.",
             "- This workflow does not publish social posts.", ""]
    if queries_used:
        lines += ["## Daraz search queries generated from live signals"] + [f"- {q}" for q in queries_used] + [""]
    if trends:
        lines += ["## Google Trends Pakistan signals"] + [f"- {p['topic']} (traffic: {p.get('approx_traffic') or 'not provided'})" for p in trends[:15]] + [""]
    if social:
        lines += ["## Public social discussion signals"] + [f"- [{p.get('community')}] {p['title']} (score {p.get('score')}, comments {p.get('comments')}) {p['url']}" for p in social[:12]] + [""]
    if tiktok:
        lines += ["## TikTok product trend signals (global tracker; not Pakistan-specific)"] + [f"- {p['title']} — {p['total_views']} — {p['creator']} — posted {p['posted']} — {p['source_url']}" for p in tiktok[:10]] + [""]
    if products:
        lines += ["## Daraz candidates"]
        for i,p in enumerate(products,1):
            lines += [f"### Candidate {i}: {p['title']}", f"- Search query: {p['search_query']}",
                      f"- Listing: {p['url']}", f"- Verification: {p['verification']}",
                      f"- Cloudinary image: {p.get('public_image_url') or 'not available'}", ""]
    else:
        lines += ["## Daraz matching result", "No reliable Daraz listing candidates extracted; no generic ideas substituted.", ""]
    lines += ["## Errors / limitations"] + ([f"- {e}" for e in errors] if errors else ["- None recorded."])
    return "\n".join(lines) + "\n"

def main():
    errors = []
    trends, err = fetch_google_trends()
    if err: errors.append("Google Trends: " + err)
    social, social_errors = fetch_social_signals()
    errors += ["Reddit feed: " + e for e in social_errors[:3]]
    tiktok, tiktok_error = fetch_tiktok_trend_signals()
    if tiktok_error: errors.append("TikTok trend tracker: " + tiktok_error)
    products = []
    queries_used = []
    try:
        queries = make_queries(trends, social, tiktok)
        queries_used = queries
        if not queries: errors.append("AI returned no defensible product queries.")
        for q in queries:
            matches, e = search_daraz(q)
            if e: errors.append(f"Daraz search '{q}': {e}")
            products.extend(matches)
            if len(products) >= 15: break
            time.sleep(2)
    except Exception as e:
        errors.append("AI trend-to-product matching: " + str(e)[:220])
    unique = {}
    for p in products: unique.setdefault(p["url"], p)
    products = list(unique.values())[:15]
    for p in products:
        try:
            p["social_copy"] = create_social_copy(p)
        except Exception as e:
            p["social_copy_error"] = str(e)[:200]
        image_url, image_error = upload_product_image_to_cloudinary(p["url"])
        p["public_image_url"] = image_url or ""
        if image_error: p["image_upload_error"] = image_error
    report = build_report(trends, social, tiktok, products, errors, queries_used)
    if queries_used:
        print("Daraz search queries: " + " | ".join(queries_used))
    with open("trend_report.md","w",encoding="utf-8") as f: f.write(report)
    with open("daraz_candidates.json","w",encoding="utf-8") as f:
        json.dump({"generated_at":datetime.now(timezone.utc).isoformat(),"count":len(products),"items":products},f,ensure_ascii=False,indent=2)
    print(report)
    print(f"Saved {len(products)} Daraz listing candidates.")

if __name__ == "__main__":
    main()
