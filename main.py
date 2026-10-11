import os
import time
from google import genai
from google.genai.errors import ServerError

api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY is not set")

client = genai.Client(api_key=api_key)

prompt = """
You are Trend Hunter AI for the Trending Finds brand.

Suggest 5 product ideas with strong buying potential.

Focus on:
- Mobile accessories
- Gadgets
- Useful home products
- Fashion
- Beauty and lifestyle

For each idea, provide:
1. Product name
2. Why customers may want it
3. Target customer
4. Marketing angle
5. Professional social media caption
6. Five relevant hashtags

Do not invent prices, ratings, sales figures, or product links.
Clearly label suggestions as ideas, not verified live trends.
"""

models = [
    "gemini-3.6-flash",
    "gemini-3.5-flash"
]

for model in models:
    for attempt in range(2):
        try:
            print(f"Trying {model}, attempt {attempt + 1}")

            response = client.models.generate_content(
                model=model,
                contents=prompt
            )

            print("\n===== TREND HUNTER AI =====\n")
            print(response.text)
            print("\n===== END =====")
            raise SystemExit(0)

        except ServerError as error:
            print(f"Temporary AI service error: {error}")

            if attempt == 0:
                time.sleep(10)

print("AI service is temporarily unavailable.")
print("The next scheduled run can try again.")
raise SystemExit(0)
