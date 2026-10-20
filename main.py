import os
import time
from datetime import datetime, timezone

from google import genai
from google.genai.errors import ServerError

api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError(
        "GEMINI_API_KEY secret is not configured in GitHub."
    )

client = genai.Client(api_key=api_key)

prompt = """
You are Trend Hunter AI, the product research assistant
for the Trending Finds online business.

Suggest 5 product ideas that may suit customers in Pakistan.

Focus on:
- Mobile accessories
- Useful gadgets
- Home products
- Fashion
- Beauty and lifestyle

For each idea, provide:
1. Product name
2. Why customers might want it
3. Target customer
4. Marketing angle
5. A professional Facebook/Instagram caption
6. Five relevant hashtags

Rules:
- Do not invent prices, ratings, sales figures, or affiliate links.
- Do not claim you checked live trends or real sales data.
- Clearly label these as ideas, not verified bestsellers.
- Reply in clear, practical English.
"""

models = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
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

            if response.text:
                report = response.text
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
    f"Generated: {timestamp}\n\n"
    "**Note:** These are AI-generated ideas, "
    "not verified live trends or sales data.\n\n"
    + report
    + "\n"
)

with open("trend_report.md", "w", encoding="utf-8") as file:
    file.write(full_report)

print("\n===== TREND HUNTER REPORT =====\n")
print(full_report)
print("\nReport saved to trend_report.md")
                                             
