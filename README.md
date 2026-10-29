# Trend Hunter AI

Trend Hunter is a Pakistan-focused affiliate research assistant for **Trending Finds**.

## What it does now

- Fetches the public Google Trends Pakistan RSS feed when available.
- Uses Gemini to create a dated product-opportunity report with ready-to-edit Facebook, Instagram and TikTok copy.
- Clearly separates trend signals from unverified product hypotheses.
- Saves reports as `trend_report.md` and archives them in `reports/` through GitHub Actions.
- Provides a FastAPI chat backend at `/chat` and a simple mobile-friendly chat page at `/`.

## Important limits

- Google Trends search interest is not proof that a product sells.
- The app does **not** yet connect to Daraz's private affiliate account or automatically verify listings, commission rates, product URLs, orders, or earnings.
- The report generator does **not** automatically publish posts to social media. Social publishing requires authorized platform APIs and account permissions.
- Never put API keys in source code or commit them to Git.

## Required secret

In GitHub, open **Settings → Secrets and variables → Actions → New repository secret** and create:

- Name: `GEMINI_API_KEY`
- Value: your Gemini API key

Keep the value private.

## Run report generator

In GitHub, open **Actions → Trend Hunter AI → Run workflow**. The workflow also runs every 6 hours. Each successful run creates a report and saves a dated copy under `reports/`.

## Run the chat app

Python 3.11+ is recommended.

```bash
pip install -r requirements.txt
export GEMINI_API_KEY="your-key"
uvicorn app:app --host 0.0.0.0 --port 8000
```

On Windows, set `GEMINI_API_KEY` through your environment variables before starting Uvicorn.

For a hosted deployment, set `GEMINI_API_KEY` as a private environment variable in the hosting dashboard. Do not put it in `render.yaml` or frontend code. The included `render.yaml` provides a basic Render web-service configuration.

## Next development stages

1. Test the report workflow and inspect real output.
2. Add verified Daraz product data and affiliate-link handling using an authorized/official method where available.
3. Add approved social publishing integrations.
4. Add real analytics and order reporting only after the relevant accounts and APIs are connected.
