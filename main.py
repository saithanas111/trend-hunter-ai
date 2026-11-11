import os, re, json, time, html, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
from io import BytesIO
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
REDDIT_FEEDS = [
    "https://www.reddit.com/r/gadgets/hot.json?limit=15",
    "https://www.reddit.com/r/DidntKnowIWantedThat/hot.json?limit=15",
]
APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "").strip()
INSTAGRAM_TREND_HASHTAGS = [x.strip().lstrip("#") for x in os.environ.get(
    "INSTAGRAM_TREND_HASHTAGS", "productfinds,trendinggadgets,gadgets,portableblender,kashmiribangles"
).split(",") if x.strip()][:5]

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



RESEARCHED_DARAZ_MATCHES = {
    "xiaomi 120w 67w 33w turbo charger cable": [{
        "title": "100% Original Xiaomi 120W, 67W, 33W Turbo Charger Cable 6A",
        "url": "https://www.daraz.pk/products/13-1211s-10-10-10s-9-100-w-120w-33w-67w-120w-6a-i491483422.html",
        "affiliate_url": "https://s.daraz.pk/s.230Dt?cc",
        "source_image_url": "https://img.drz.lazcdn.com/g/kf/S852f26d5ebd04777b9604812e87f54c0I.jpg_720x720q80.jpg_.webp",
        "source": "User-selected Daraz affiliate product; public Daraz listing image",
        "verification": "User confirmed their affiliate shortlink is for the Xiaomi Turbo cable shown in their Daraz screenshot. A public Daraz search snapshot on 2026-11-07 showed a matching listing at Rs. 549, 4.9/5 from 523 ratings and 2.4K sold, seller E-Z Cart; user's screenshot showed Rs. 527. Price may vary. Product authenticity and exact compatibility are not independently verified."
    }],
    "90 degree USB C elbow charging cable": [{
        "title": "Essager 7A USB Type C Cable 90 Degree For 100W Fast Charging Cord",
        "url": "https://www.daraz.pk/products/7-90-100-i1954838080.html",
        "source_image_url": "https://img.drz.lazcdn.com/g/kf/S84b4d1b7bff947af99284def5cb4a3a0Y.jpg_720x720q80.jpg_.webp",
        "source": "Daraz Pakistan public product and category pages; manually researched current match",
        "verification": "Category-level match to the viral TikTok 90-degree 100W cable trend (not the same brand/model). Daraz snapshot 2026-11-07: Rs 1,320; 5.0/5 from 32 ratings; about 1.0K sold; seller Buy More Save More Store; seller positive rating 87%; ship-on-time 100%; 14-day easy return; no warranty. Listing stock and affiliate eligibility still require live/account verification.",
    }]
}

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


def public_metric_number(value):
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value or "").strip().replace(",", "").upper()
    try:
        multiplier = 1
        if raw.endswith("K"):
            multiplier, raw = 1_000, raw[:-1]
        elif raw.endswith("M"):
            multiplier, raw = 1_000_000, raw[:-1]
        elif raw.endswith("B"):
            multiplier, raw = 1_000_000_000, raw[:-1]
        return float(raw) * multiplier
    except Exception:
        return 0.0


def parse_public_post_date(value):
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        raw = str(value).strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(raw)
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except Exception:
        return None


def fetch_instagram_public_signals():
    """Optional public Instagram hashtag research via Apify; never accesses private data."""
    if not APIFY_API_TOKEN:
        return [], ["Instagram public trend source skipped: APIFY_API_TOKEN is not configured."]
    hashtags = INSTAGRAM_TREND_HASHTAGS
    if not hashtags:
        return [], ["Instagram public trend source skipped: no hashtags configured."]
    endpoint = (
        "https://api.apify.com/v2/acts/instagram-data-api~instagram-scraper/"
        "run-sync-get-dataset-items?token=" + urllib.parse.quote(APIFY_API_TOKEN) +
        "&timeout=120&memory=1024"
    )
    payload = {
        "directUrls": [f"https://www.instagram.com/explore/tags/{tag}/" for tag in hashtags],
        "resultsType": "posts",
        "resultsLimit": 10,
        "skipPinnedPosts": True,
        "onlyPostsNewerThan": "7 days",
    }
    request = urllib.request.Request(
        endpoint, data=json.dumps(payload).encode("utf-8"),
        headers={**HEADERS, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=135) as response:
            rows = json.loads(response.read().decode("utf-8"))
        if not isinstance(rows, list):
            raise ValueError("Apify returned an unexpected dataset format.")
        now = datetime.now(timezone.utc)
        out = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            post_url = row.get("url") or row.get("postUrl") or row.get("post_url")
            caption = str(row.get("caption") or row.get("text") or "").strip()
            posted = parse_public_post_date(
                row.get("takenAt") or row.get("timestamp") or row.get("taken_at") or row.get("createdAt")
            )
            if not post_url or not str(post_url).startswith("https://www.instagram.com/") or not posted:
                continue
            age_days = (now - posted).total_seconds() / 86400
            if age_days < -0.25 or age_days > 7:
                continue
            username = row.get("ownerUsername") or row.get("username") or "unknown"
            tag = next((tag for tag in hashtags if f"/{tag.lower()}/" in str(post_url).lower()), hashtags[0])
            views = row.get("views") or row.get("videoViewCount") or row.get("video_view_count")
            likes = row.get("likes") or row.get("likesCount") or row.get("like_count")
            comments = row.get("comments") or row.get("commentsCount") or row.get("comment_count")
            title = caption[:220] if caption else f"Public Instagram post by @{username}"
            out.append({
                "title": title,
                "community": f"Instagram public hashtag #{tag}",
                "score": likes or 0,
                "comments": comments or 0,
                "views": views,
                "username": username,
                "timestamp": posted.isoformat(),
                "url": str(post_url),
                "source": "Instagram public hashtag feed via Apify",
            })
        out.sort(key=lambda x: (public_metric_number(x.get("views")), public_metric_number(x.get("score")), public_metric_number(x.get("comments"))), reverse=True)
        return out[:50], []
    except Exception as e:
        return [], ["Instagram public trend source (Apify): " + str(e)[:220]]


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
    urls = [
        "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote("site:daraz.pk/products " + query),
        "https://search.brave.com/search?q=" + urllib.parse.quote("site:daraz.pk/products " + query),
        "https://www.google.com/search?q=" + urllib.parse.quote("site:daraz.pk/products " + query),
        "https://www.bing.com/search?q=" + urllib.parse.quote("site:daraz.pk/products " + query),
        "https://www.daraz.pk/catalog/?q=" + urllib.parse.quote(query),
    ]
    urls += ["https://www.daraz.pk/tag/" + tag + "/" for tag in special_tags.get(query.lower(), [slug])[:2]]
    seen, found = set(), []
    diagnostics = []
    for search_url in urls:
        try:
            raw = fetch_url(search_url, 12).decode("utf-8", "ignore")
            parser = ProductParser()
            parser.feed(raw)
            candidates = list(parser.links)
            normalized = urllib.parse.unquote(html.unescape(raw)).replace("\\/", "/").replace("\\u002F", "/")
            pattern = r'(?:(?:https?:)?//www\.daraz\.pk)?/products/[^"\\<>\s]+?-i\d+(?:-s\d+)?\.html'
            embedded = re.findall(pattern, normalized, flags=re.I)
            candidates += [{"url": u, "title": ""} for u in embedded]
            diagnostics.append(f"{search_url.split('/')[2]}: {len(raw)} bytes, {len(parser.links)} anchor links, {len(embedded)} embedded URLs, /products/ tokens={raw.count('/products/')}")
            for p in candidates:
                link = urljoin("https://www.daraz.pk", html.unescape(p["url"])).split("?")[0]
                if not re.match(r"^https://www\.daraz\.pk/products/.+-i\d+(?:-s\d+)?\.html$", link, re.I) or link in seen:
                    continue
                seen.add(link)
                title = re.sub(r"[-_]+", " ", p.get("title") or "")
                title = re.sub(r"\s+", " ", title).strip() or query
                found.append({"title": title[:240], "url": link, "search_query": query,
                              "source": "Daraz Pakistan listing or indexed public search result",
                              "verification": "Listing URL extracted only; seller, price, stock, reviews and affiliate eligibility NOT verified."})
                if len(found) >= limit:
                    return found, None
        except Exception as e:
            diagnostics.append(f"{search_url.split('/')[2]}: {str(e)[:120]}")
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

def make_queries(trends, social, tiktok=None):
    """Return only product queries tied to an exact live signal in the supplied sources."""
    # Google Trends is search-interest context, not social-platform proof.
    # Only live public social-platform posts may qualify a product candidate.
    signals = []
    for item in social:
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        if title and url:
            signals.append({
                "title": title,
                "source": item.get("source") or "Reddit public hot posts",
                "url": url,
                "metric": f"views={item.get('views')}; likes={item.get('score')}; comments={item.get('comments')}; posted={item.get('timestamp')}",
            })
    if not signals:
        return []

    prompt = (
        "Return ONLY a JSON array of up to 8 objects with keys query, signal_title, signal_source, signal_url. "
        "Each query must be a physical product explicitly evidenced by one supplied signal. "
        "Copy signal_title, signal_source and signal_url EXACTLY from one supplied signal. "
        "Do not invent trends, brands, popularity, sales or evidence. Ignore general news and non-product topics. "
        "If no clear product is evidenced, return []. Signals:\\n" +
        json.dumps(signals, ensure_ascii=False)
    )
    vals = parse_json(gemini_text(prompt), "array")
    known = {(x["title"], x["source"], x["url"]): x for x in signals}
    out, seen = [], set()
    for item in vals:
        if not isinstance(item, dict):
            continue
        query = str(item.get("query") or "").strip()[:100]
        key = (
            str(item.get("signal_title") or "").strip(),
            str(item.get("signal_source") or "").strip(),
            str(item.get("signal_url") or "").strip(),
        )
        evidence = known.get(key)
        if not query or not evidence or query.casefold() in seen:
            continue
        seen.add(query.casefold())
        out.append({"query": query, "trend_evidence": evidence})
    return out[:8]

def create_social_copy(product):
    prompt = ("Write safe, concise copy for this Daraz listing candidate. Return ONLY JSON with keys "
              "facebook_caption, instagram_caption, reel_hook, video_script, hashtags (array of 5). "
              "Do not claim viral/best-selling/discounted/tested/in-stock; do not invent price or features.\n"
              + json.dumps({"title": product["title"], "url": product["url"]}, ensure_ascii=False))
    data = parse_json(gemini_text(prompt), "object")
    for key in ("facebook_caption", "instagram_caption", "reel_hook", "video_script", "hashtags"):
        if not data.get(key): raise ValueError("Missing copy field: " + key)
    cta = "Comment ORDER to request the product link."
    for key in ("facebook_caption", "instagram_caption"):
        data[key] = data[key].strip().rstrip() + "\n\n" + cta
    return data


def fallback_social_copy(product):
    title = re.sub(r"\s+", " ", product.get("title", "Daraz product")).strip()[:180]
    safe_line = "Check the product details, compatibility and latest availability on the listing before ordering."
    hashtags = ["#DarazPakistan", "#TrendingFinds", "#OnlineShopping", "#ProductFinds", "#Pakistan"]
    return {
        "facebook_caption": f"{title}\n\n{safe_line}\n\nComment ORDER to request the product link.",
        "instagram_caption": f"{title}\n\nExplore the listing for full details.\n{safe_line}\n\nComment ORDER to request the product link.",
        "reel_hook": f"Looking for {title.lower()}?",
        "video_script": f"Show the product clearly. On-screen text: {title}. End card: Check the listing for details and compatibility.",
        "hashtags": hashtags,
    }

def upload_product_image_to_cloudinary(product):
    image = product.get("source_image_url")
    if not image:
        try:
            page = fetch_url(product["url"], 20).decode("utf-8", "ignore")
            m = re.search(r"<meta[^>]+(?:property=['\"]og:image['\"][^>]+content=['\"]([^'\"]+)|content=['\"]([^'\"]+)['\"][^>]+property=['\"]og:image)", page, re.I)
            image = (m.group(1) or m.group(2)) if m else None
        except Exception as e:
            return None, "Could not read product page image: " + str(e)[:160]
    if not image:
        return None, "No public product image found."
    cloudinary_error = None
    if all(CLOUDINARY.values()):
        try:
            import cloudinary, cloudinary.uploader
            cloudinary.config(cloud_name=CLOUDINARY["CLOUDINARY_CLOUD_NAME"],
                              api_key=CLOUDINARY["CLOUDINARY_API_KEY"],
                              api_secret=CLOUDINARY["CLOUDINARY_API_SECRET"], secure=True)
            result = cloudinary.uploader.upload(html.unescape(image),
                                                 folder="trend-hunter/products", resource_type="image", format="jpg")
            if result.get("secure_url"):
                return result["secure_url"], None
        except Exception as e:
            cloudinary_error = str(e)[:160]
    # Public-repository fallback: convert to JPEG and commit under assets/products.
    try:
        from PIL import Image
        image_bytes = fetch_url(html.unescape(image), 25)
        picture = Image.open(BytesIO(image_bytes)).convert("RGB")
        product_id = re.search(r"-i(\d+)", product.get("url", ""))
        filename = "daraz-" + (product_id.group(1) if product_id else re.sub(r"[^a-z0-9]+", "-", product.get("title", "product").lower())[:48]) + ".jpg"
        relative = Path("assets") / "products" / filename
        relative.parent.mkdir(parents=True, exist_ok=True)
        picture.save(relative, format="JPEG", quality=92, optimize=True)
        public_url = "https://raw.githubusercontent.com/saithanas111/trend-hunter-ai/main/" + relative.as_posix()
        note = "JPEG stored in public GitHub assets for social publishing."
        if cloudinary_error:
            note += " Cloudinary fallback used: " + cloudinary_error
        elif not all(CLOUDINARY.values()):
            note += " Cloudinary credentials were not configured."
        return public_url, note
    except Exception as e:
        return None, "Image hosting failed: " + str(e)[:180]

def build_report(trends, social, tiktok, products, errors, queries_used=None):
    lines = ["# Trend Hunter AI Report", "",
             "**Generated:** " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "",
             "**AI models attempted:** " + ", ".join(MODELS), "",
             "## Live research status",
             f"- Google Trends Pakistan topics fetched: {len(trends)}",
             "- Google Trends is search-interest context only; it does not qualify products as social trends.",
             f"- Public social-post signals fetched: {len(social)}",
             f"- Instagram public hashtag signals: {sum(1 for p in social if p.get('source') == 'Instagram public hashtag feed via Apify')}",
             f"- Reddit public hot-post signals: {sum(1 for p in social if p.get('source') == 'Reddit public hot posts')}",
             "- TikTok trend signals: not used, per the current platform instruction.",
             f"- Daraz listing candidates matched: {len(products)}",
             f"- Public product images hosted: {sum(bool(p.get('public_image_url')) for p in products)}",
             "- Trend/search signals are not proof of Pakistan sales.",
             "- Daraz listing extraction does not verify seller quality, price, stock, reviews, delivery or affiliate eligibility.",
             "- Affiliate deeplinks are not generated; no supported Daraz affiliate API has been confirmed.",
             "- This workflow does not publish social posts.", ""]
    if queries_used:
        lines += ["## Daraz search queries generated from live signals"] + [f"- {q}" for q in queries_used] + [""]
    if trends:
        lines += ["## Google Trends Pakistan signals"] + [f"- {p['topic']} (traffic: {p.get('approx_traffic') or 'not provided'})" for p in trends[:15]] + [""]
    if social:
        lines += ["## Public social discussion signals"] + [f"- [{p.get('community')}] {p['title']} (views {p.get('views', 'not provided')}, likes {p.get('score')}, comments {p.get('comments')}, posted {p.get('timestamp', 'date unavailable')}) {p['url']}" for p in social[:20]] + [""]
    if products:
        lines += ["## Daraz candidates"]
        for i,p in enumerate(products,1):
            lines += [f"### Candidate {i}: {p['title']}", f"- Search query: {p['search_query']}",
                      f"- Listing: {p['url']}", f"- Verification: {p['verification']}",
                      f"- Trend evidence: {json.dumps(p.get('trend_evidence') or {}, ensure_ascii=False)}",
                      f"- Public image: {p.get('public_image_url') or 'not available'}", ""]
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
    instagram_signals, instagram_errors = fetch_instagram_public_signals()
    social.extend(instagram_signals)
    errors += instagram_errors[:2]
    # TikTok is intentionally not accessed or used in this project phase.
    tiktok = []
    products = []
    queries_used = []
    try:
        query_items = make_queries(trends, social)
        queries_used = [item["query"] for item in query_items]
        if not query_items: errors.append("No product queries were defensibly linked to a live public social post.")
        for candidate in query_items:
            q = candidate["query"]
            evidence = candidate["trend_evidence"]
            researched_key = q.strip().casefold()
            if researched_key in RESEARCHED_DARAZ_MATCHES:
                products.extend([dict(item, search_query=q, trend_evidence=evidence) for item in RESEARCHED_DARAZ_MATCHES[researched_key]])
                continue
            matches, e = search_daraz(q)
            if e: errors.append(f"Daraz search '{q}': {e}")
            for match in matches:
                match["trend_evidence"] = evidence
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
            p["social_copy"] = fallback_social_copy(p)
            p["social_copy_error"] = str(e)[:200]
        image_url, image_error = upload_product_image_to_cloudinary(p)
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
