# Trend Hunter AI

Trend Hunter is a Pakistan-focused affiliate research assistant for **Trending Finds**.

## What it does now

- Fetches the public Google Trends Pakistan RSS feed when available.
- Uses Gemini to create a dated product-opportunity report for the connected Facebook Page and Instagram professional profile only.
- Uses public Instagram product-trend signals only when a direct public Reel permalink, product mention, observable view metric and creator-relative performance above 1.0x usual are present; raw views alone do not qualify. Google Trends is context, not social-trend proof.
- Unverified Daraz candidates remain research-only. Captions and product media are not created until exact listing, stock, seller and affiliate-link checks are fresh and explicitly verified.
- Clearly separates trend signals from unverified product hypotheses.
- Saves reports as `trend_report.md` and archives them in `reports/` through GitHub Actions.
- Provides a FastAPI chat backend at `/chat` and a simple mobile-friendly chat page at `/`.

## Important limits

- Google Trends search interest is not proof that a product sells.
- The app does **not** yet connect to Daraz's private affiliate account or automatically verify listings, commission rates, product URLs, orders, or earnings. No affiliate URL is invented or reused from an older product.
- The research workflow itself does not publish; a separate fail-closed Meta workflow can publish only approved, fully verified video queue items when the platform-specific enable flags and credentials are configured.
- The project does not collect TikTok or Reddit trend data; only Facebook and Instagram are in scope.
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

## Instagram publishing (approval-gated)

The Meta publishing workflow runs automatically after a successful Trend Hunter AI run and can also be manually dispatched. It is deliberately disabled unless the relevant platform-specific flags and credentials are configured.

Add these repository secrets under **Settings → Secrets and variables → Actions**:

- `AUTO_PUBLISH_ENABLED`: set to `true` only when you intentionally enable publishing.
- `META_IG_USER_ID`: the Instagram professional account ID authorized for the Meta Graph API.
- `META_ACCESS_TOKEN`: a valid Meta access token with the required Instagram publishing permissions.

The account connected to Windsor.ai is not automatically a Meta Graph API token for GitHub Actions. Do not paste access tokens into chat or commit them to this repository.

Before a queue item can publish, its JSON entry must explicitly contain:
- `verified: true` after checking the real listing, seller, price, stock, terms and affiliate eligibility.
- `approved: true` after approving the exact caption and creative.
- A valid `affiliate_url`.
- A public HTTPS `public_video_url` pointing to an MP4/MOV video, marked `true_3d_cgi` and reviewed.
- A `9:16` vertical aspect ratio and a quality manifest confirming four distinct camera angles, genuine 3D product motion, studio lighting, close-ups, transitions, and no static-image zoom.
- A direct social post trend metric showing more than `1.0x creator usual`; raw views alone do not qualify.

New queue entries are always created with `verified: false` and `approved: false`. The Meta publishing workflow can be manually dispatched or automatically triggered after a successful Trend Hunter AI run; it never publishes drafts or items that fail the queue gate. Successful and failed attempts are recorded in `publish_status.json`.


## Strict trend qualification and Meta publishing

- Raw Instagram hashtag hits are research observations, not trends. They are excluded from product matching unless a direct public Instagram product Reel is independently verified as above the creator's usual performance.
- The current product-trend gate requires a direct Instagram post URL, an explicit product list, a view metric, and creator-relative performance greater than 1.0x usual.
- Google Trends is search context only; it never qualifies a social product trend.
- The follow-up Meta publishing workflow runs after a successful Trend Hunter workflow. It publishes only items that pass `queue_gate.py`, including exact Daraz brand/variant, fresh listing checks, verified affiliate URL, and a reviewed `true_3d_cgi` video.
- Instagram is locked to `@official.trending.finds`. Facebook publishing is locked to Page `Trending Finds` (ID `1212885835249403`). A live identity mismatch stops publishing.
- Instagram publishing requires repository secrets `AUTO_PUBLISH_ENABLED=true`, `META_IG_USER_ID`, and `META_ACCESS_TOKEN`.
- Facebook Page video publishing requires repository secrets `FACEBOOK_AUTO_PUBLISH_ENABLED=true` and `FACEBOOK_PAGE_ACCESS_TOKEN`. The Page ID is fixed in the workflow and publisher.
- No 2.5D still-image zoom is accepted as a video. Profile editing and automatic Meta DMs are not configured.
- Publishing status is keyed by the Daraz listing URL, not the queue position, to avoid suppressing a different product after queue reordering.
- A shared Pakistan-local daily log caps publishing at five distinct Daraz listings from five different brands across both Instagram and Facebook combined. The same product may be published to the second platform without counting twice.
- The daily log records the Daraz listing, brand, verification snapshot, trend evidence, creative checks, platform IDs, and placeholders for comments, DM outcomes and metrics.


Publishable video items must also include a reviewed `9:16` vertical MP4/MOV and a quality manifest confirming at least four distinct camera angles, genuine 3D product motion, studio lighting, close-ups, transitions, and no static-image zoom. The trend metric must explicitly show more than `1.0x creator usual`; raw views and likes alone cannot pass the queue gate.
