import os, re, json, time, html, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urljoin
from datetime import datetime, timezone
from google import genai

API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY) if API_KEY else None
MODELS = [m.strip() for m in os.environ.get("GEMINI_MODELS", os.environ.get("GEMINI_MODEL", "gemini-2.0-flash,gemini-2.0-flash-lite")).split(",") if m.strip()]
CLOUDINARY = {k: os.environ.get(k) for k in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")}
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125 Safari/537.36"}
TRENDS_URL = "https://trends.google.com/trending/rss?geo=PK"
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
    url = "https://www.daraz.pk/catalog/?q=" + urllib.parse.quote(query)
    try:
        raw = fetch_url(url, 25).decode("utf-8", "ignore")
        parser = ProductParser()
        parser.feed(raw)
        candidates = list(parser.links)
        # Daraz pages often embed product cards in JSON rather than ordinary anchor text.
        # Extract canonical product URLs from that embedded page data as a second path.
        pattern = r'(?:(?:https?:)?\\?/\\?/www\\.daraz\\.pk)?\\?/products\\?/[^"\\\\<> ]+?-i\\d+-s\\d+\\.html(?:[^"\\\\<> ]*)?'
        for match in re.findall(pattern, raw, flags=re.I):
            candidates.append({"url": match.replace("\\\\/", "/"), "title": ""})
        seen, found = set(), []
        for p in candidates:
            link = urljoin("https://www.daraz.pk", html.unescape(p["url"])).split("?")[0]
            if not re.match(r"^https://www\\.daraz\\.pk/products/.+-i\\d+-s\\d+\\.html$", link, re.I) or link in seen:
                continue
            seen.add(link)
            title = re.sub(r"[-_]+", " ", p.get("title") or "")
            title = re.sub(r"\\s+", " ", title).strip() or query
            found.append({"title": title[:240], "url": link, "search_query": query,
                          "source": "Daraz Pakistan search page embedded product data",
                          "verification": "Listing URL extracted only; seller, price, stock, reviews and affiliate eligibility NOT verified."})
            if len(found) >= limit: break
        return found, None
    except Exception as e:
        return [], str(e)[:200]

def gemini_text(prompt):
    if not client:
        raise RuntimeError("GEMINI_API_KEY is missing.")
    failures = []
    for model in MODELS:
        for attempt in range(2):
            try:
                response = client.models.generate_content(model=model, contents=prompt)
                if response.text and response.text.strip():
                    return response.text.strip()
                failures.append(f"{model}: empty response")
            except Exception as e:
                message = str(e)[:180]
                failures.append(f"{model}: {message}")
                # Retry transient rate-limit / service errors once, then try the fallback model.
                if attempt == 0 and any(code in message.lower() for code in ("503", "429", "unavailable", "high demand", "deadline")):
                    time.sleep(5)
                    continue
                break
    raise RuntimeError("All configured Gemini models failed: " + " | ".join(failures[-4:]))

def parse_json(text, kind):
    match = re.search(r"\[[\s\S]*\]" if kind == "array" else r"\{[\s\S]*\}", text)
    if not match: raise ValueError("Gemini did not return valid JSON.")
    return json.loads(match.group(0))

def make_queries(trends, social):
    prompt = ("From these current Pakistan search and public discussion signals, return ONLY a JSON array of up to 8 "
              "physical product search queries clearly connected to the signals. Do not invent trends or demand. "
              "Return [] if no defensible product match. Signals:\n" +
              json.dumps({"google_trends": trends[:15], "social_posts": social[:15]}, ensure_ascii=False))
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

def build_report(trends, social, products, errors):
    lines = ["# Trend Hunter AI Report", "",
             "**Generated:** " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "",
             "**AI models attempted:** " + ", ".join(MODELS), "",
             "## Live research status",
             f"- Google Trends Pakistan topics fetched: {len(trends)}",
             f"- Public Reddit hot-post signals fetched: {len(social)}",
             f"- Daraz listing candidates extracted: {len(products)}",
             f"- Product images uploaded to Cloudinary: {sum(bool(p.get('public_image_url')) for p in products)}",
             "- Trend/search signals are not proof of Pakistan sales.",
             "- Daraz listing extraction does not verify seller quality, price, stock, reviews, delivery or affiliate eligibility.",
             "- Affiliate deeplinks are not generated; no supported Daraz affiliate API has been confirmed.",
             "- This workflow does not publish social posts.", ""]
    if trends:
        lines += ["## Google Trends Pakistan signals"] + [f"- {p['topic']} (traffic: {p.get('approx_traffic') or 'not provided'})" for p in trends[:15]] + [""]
    if social:
        lines += ["## Public social discussion signals"] + [f"- [{p.get('community')}] {p['title']} (score {p.get('score')}, comments {p.get('comments')}) {p['url']}" for p in social[:12]] + [""]
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
    errors += ["Social feed: " + e for e in social_errors[:3]]
    products = []
    try:
        queries = make_queries(trends, social)
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
    report = build_report(trends, social, products, errors)
    with open("trend_report.md","w",encoding="utf-8") as f: f.write(report)
    with open("daraz_candidates.json","w",encoding="utf-8") as f:
        json.dump({"generated_at":datetime.now(timezone.utc).isoformat(),"count":len(products),"items":products},f,ensure_ascii=False,indent=2)
    print(report)
    print(f"Saved {len(products)} Daraz listing candidates.")

if __name__ == "__main__":
    main()
