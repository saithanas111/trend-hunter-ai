import os
import time
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from google import genai

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not configured in GitHub Secrets.")

client = genai.Client(api_key=API_KEY)
TRENDS_URL = "https://trends.google.com/trending/rss?geo=PK"


def fetch_pakistan_trends(limit=15):
    """Fetch public Google Trends RSS items. Empty list is handled honestly."""
    request = urllib.request.Request(
        TRENDS_URL,
        headers={"User-Agent": "TrendHunterAI/1.0 (trend research)"}
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)
        items = []
        for item in root.findall(".//item")[:limit]:
            title = (item.findtext("title") or "").strip()
            traffic = (item.findtext("ht:approx_traffic", default="", namespaces={"ht": "https://trends.google.com/trending/rss"}) or "").strip()
            if title:
                items.append({"topic": title, "approx_traffic": traffic or "not provided"})
        return items, None
    except Exception as exc:
        print(f"Trend feed unavailable: {exc}")
        return [], str(exc)[:180]


trends, trend_error = fetch_pakistan_trends()
if trends:
    trend_context = json.dumps(trends, ensure_ascii=False, indent=2)
    trend_status = "Google Trends Pakistan RSS was fetched successfully. It is a search-interest signal, not proof of product demand or sales."
else:
    trend_context = "No live trend items could be fetched during this run."
    trend_status = "Live trend feed unavailable; do not pretend the report contains verified current trends."

prompt = f"""
You are Trend Hunter AI, the honest research and content assistant for Trending Finds,
a Pakistan-focused Daraz affiliate marketing project.

LIVE TREND INPUT (Google Trends Pakistan RSS):
{trend_context}

DATA STATUS:
{trend_status}

Create EXACTLY 10 distinct product/content opportunities that could be tested on Daraz Pakistan. This is mandatory: do not stop after 5. Use headings exactly "## Opportunity 1: [product name]" through "## Opportunity 10: [product name]". Keep each item concise enough that all ten fit in one response while including every required field.
Use the live topics only when there is a sensible connection to a product. Do not force irrelevant trends.
If no relevant trend-to-product connection exists, label the product suggestion as an evergreen hypothesis.

For each opportunity provide:
1. Product category and specific search terms the owner can use on Daraz.
2. Related trend topic, or clearly label it "Evergreen hypothesis".
3. Why it may interest a Pakistani audience (hypothesis, not proven demand).
4. Target customer and marketing angle.
5. Facebook caption, Instagram caption, TikTok hook, and 15-30 second video script.
6. Five relevant hashtags.
7. A product verification checklist: seller reliability, current price, reviews, sold count if shown, stock, shipping, return policy, and affiliate eligibility.
8. Affiliate URL: write "ADD VERIFIED DARAZ AFFILIATE LINK" because no verified link was supplied.

After Opportunity 10, include: best first test and why; a suggested schedule for 10-20 varied daily posts across platforms without spam; three engagement experiments; a reusable tracking table template for clicks, messages, orders and commissions; and a short list of what is still unverified. Before finishing, verify that all ten numbered opportunity headings are present. Do not suggest publishing the identical post repeatedly.

Rules:
- Never invent Daraz listings, prices, ratings, sold counts, commission rates, URLs, views, orders, or earnings.
- Google Trends is a search-interest signal, not product sales proof.
- No automatic social posts are published by this script.
- Keep it practical, honest, and in clear English.
"""

models = ["gemini-3.8-flash", "gemini-2.5-flash"]
report = None
errors = []

for model in models:
    for attempt in range(2):
        try:
            print(f"Trying {model}, attempt {attempt + 1}")
            response = client.models.generate_content(model=model, contents=prompt)
            if response.text and response.text.strip():
                report = response.text.strip()
                break
            errors.append(f"{model}: empty response")
        except Exception as exc:
            errors.append(f"{model}: {str(exc)[:180]}")
            print(f"AI request failed: {model}: {exc}")
            if attempt == 0:
                time.sleep(5)
    if report:
        break

if report:
    # Enforce the ten-opportunity requirement instead of trusting the prompt alone.
    import re
    def opportunity_numbers(text):
        # Preserve order and duplicates so repeated or out-of-order headings fail validation.
        return [int(n) for n in re.findall(r"(?im)^## Opportunity\s+(\d+)\s*:", text)]
    if opportunity_numbers(report) != list(range(1, 11)):
        print("Report did not contain all ten required headings; requesting one concise repair.")
        repair_prompt = (
            "Repair the report below. Return the complete report with EXACTLY these headings, "
            "'## Opportunity 1: ...' through '## Opportunity 10: ...', each appearing once. "
            "Keep each opportunity concise and retain the required fields. Do not invent live listings, "
            "prices, affiliate links, orders, or earnings. Preserve the report's honest data-status notes.\n\n"
            + report
        )
        try:
            repaired = client.models.generate_content(model=models[0], contents=repair_prompt)
            if repaired.text and opportunity_numbers(repaired.text.strip()) == list(range(1, 11)):
                report = repaired.text.strip()
                print("Ten-opportunity heading validation passed after repair.")
            else:
                errors.append("Generated report still failed the ten-heading validation after repair.")
        except Exception as exc:
            errors.append(f"Report repair failed: {str(exc)[:180]}")

    if opportunity_numbers(report) != list(range(1, 11)):
        raise SystemExit("Report validation failed: expected exactly Opportunity 1 through Opportunity 10.")

if not report:
    print("\n".join(errors))
    raise SystemExit("Trend Hunter could not generate a report. Check GitHub Actions logs.")

timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
source_note = (
    "Google Trends Pakistan RSS was available for this run."
    if trends else
    "Google Trends Pakistan RSS was unavailable; recommendations are not based on live trend data."
)
full_report = (
    "# Trend Hunter AI Report\n\n"
    f"**Generated:** {timestamp}\n\n"
    f"**Trend source:** {source_note}\n\n"
    "**Important:** Trend signals are not proof of product demand. Daraz listings, prices, seller quality, "
    "commission eligibility, and affiliate URLs must be verified before promotion.\n\n"
    "**Publishing status:** This run creates content only. It does not publish social posts or confirm sales.\n\n"
    f"{report}\n"
)
with open("trend_report.md", "w", encoding="utf-8") as file:
    file.write(full_report)
print(full_report)
print("Report saved to trend_report.md")
