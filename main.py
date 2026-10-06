import os
import time
from google import genai
from google.genai.errors import ServerError

api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY is not set")

client = genai.Client(api_key=api_key)

prompt = """
You are Trend Hunter AI, an expert product research and affiliate marketing agent.

Find 5 products that are currently trending or have strong buying potential.

Focus on:
- Mobile accessories
- Gadgets
- Home useful products
- Fashion products
- Beauty and lifestyle products

For each product provide:
1. Product name
2. Why it is trending
3. Target customer
4. Suggested selling angle
5. Professional social-media caption
6. 5 relevant hashtags

Do not invent exact prices, sales numbers, ratings, or product links.
Clearly say when information is unavailable.

The goal is to help the Trending Finds brand discover products for affiliate marketing.
"""

models = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash"
]

last_error = None

for model in models:
    for attempt in range(3):
        try:
            print(f"Trying {model} - attempt {attempt + 1}")

            response = client.models.generate_content(
                model=model,
                contents=prompt,
            )

            print("\n===== TREND HUNTER AI =====\n")
            print(response.text)
            print("\n===== END =====")

            raise SystemExit(0)

        except ServerError as error:
            last_error = error
            print(f"Temporary Gemini server error: {error}")

            if attempt < 2:
                wait_time = 5 * (2 ** attempt)
                print(f"Waiting {wait_time} seconds...")
                time.sleep(wait_time)

print("\nTrend Hunter AI could not connect to Gemini.")
print("Last error:", last_error)
raise SystemExit(1)
