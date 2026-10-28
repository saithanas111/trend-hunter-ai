import os
import time
from datetime import datetime, timezone

from google import genai
from google.genai.errors import ServerError

api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError(
        "GEMINI_API_KEY is not configured in GitHub Secrets."
    )

client = genai.Client(api_key=api_key)

prompt = """
You are Trend Hunter AI, the product-content assistant
for a Pakistan-focused affiliate marketing business.

Your job is to create a practical, ready-to-use daily
marketing report for the brand Trending Finds.

Generate 5 product ideas across these categories:
- Mobile accessories
- Useful gadgets
- Home products
- Fashion
- Beauty and lifestyle

For EACH product, provide:

1. Product name.
2. Why a Pakistani customer might want it.
3. Target customer.
4. Main marketing angle.
5. Facebook post caption with a clear call to action.
6. Instagram caption with a clear call to action.
7. TikTok caption with a short video hook.
8. A simple 15-30 second video script.
9. Five relevant hashtags.
10. A suggested product-image or video concept.
11. A checklist of what the owner must verify before
    promoting the product.
12. Affiliate link: write "ADD VERIFIED AFFILIATE LINK"
    because no actual affiliate link was provided.

Also include:
- The best product idea to test first and why.
- A simple posting schedule for one day.
- Three practical ways to improve engagement.
- A short checklist for tracking clicks, messages,
  orders and commissions.

IMPORTANT RULES:
- These are product ideas, not verified live trends.
- Do not invent prices, ratings, sales figures,
  product availability or affiliate links.
- Do not claim a product is a bestseller without evidence.
- Keep all content professional and easy to understand.
- Write the report in clear English.
- Make captions ready to edit and publish.
- Do not claim posts were published or orders received.
- Do not claim sales or earnings without real data.
"""

models = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
]

report = None
errors = []

for model in models:
    for attempt in range(2):
        try:
            print(f"Trying {model}, attempt {attempt + 1}")

            response = client.models.generate_content(
                model=model,
                contents=prompt,
            )

            if response.text and response.text.strip():
                report = response.text.strip()
                break

            errors.append(f"{model}: empty response")

        except ServerError as error:
            errors.append(f"{model}: {str(error)[:200]}")
            print(f"Temporary AI service error: {error}")

            if attempt == 0:
                time.sleep(10)

        except Exception as error:
            errors.append(f"{model}: {str(error)[:200]}")
            print(f"AI request failed: {error}")
            break

    if report:
        break

if not report:
    print("Trend Hunter could not generate a report.")
    print("\n".join(errors))
    raise SystemExit(1)

timestamp = datetime.now(timezone.utc).strftime(
    "%Y-%m-%d %H:%M UTC"
)

full_report = (
    "# Trend Hunter AI Report\n\n"
    f"**Generated:** {timestamp}\n\n"
    "**Data note:** These are AI-generated product "
    "ideas, not verified live trends or sales data.\n\n"
    "**Publishing note:** Captions and video scripts "
    "are prepared for review. No posts are published "
    "automatically by this script.\n\n"
    f"{report}\n"
)

with open("trend_report.md", "w", encoding="utf-8") as file:
    file.write(full_report)

print("\n===== TREND HUNTER REPORT =====\n")
print(full_report)
print("\nReport saved to trend_report.md")
