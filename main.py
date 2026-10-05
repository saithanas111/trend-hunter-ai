import os
from google import genai

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

response = client.models.generate_content(
    model="gemini-3.8-flash",
    contents=prompt,
)

print("\n===== TREND HUNTER AI =====\n")
print(response.text)
print("\n===== END =====")
