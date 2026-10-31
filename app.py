import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from google import genai

app = FastAPI(title="Trend Hunter AI", version="0.2.0")
CHAT_PAGE = Path(__file__).with_name("chat.html")


def get_client():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY secret/environment variable is not configured."
        )
    return genai.Client(api_key=key)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


@app.get("/")
def home():
    if CHAT_PAGE.exists():
        return FileResponse(CHAT_PAGE)
    return {"status": "online", "agent": "Trend Hunter AI", "chat": "chat.html is missing"}


@app.get("/health")
def health():
    return {"status": "online", "agent": "Trend Hunter AI"}


@app.post("/chat")
def chat(request: ChatRequest):
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is empty.")

    prompt = f"""
You are Trend Hunter AI, the business assistant for Trending Finds.
Address the user as Boss. The user may write in Roman Urdu, Urdu, or English;
reply in the language the user uses.

Help with Daraz affiliate research, ethical marketing, content planning, and reports.
Be honest about your capabilities: this chat cannot directly publish social posts,
inspect private Daraz affiliate account data, confirm orders, move money, or verify
a link unless an authorized integration actually provides that capability.
Never invent live trends, product statistics, prices, orders, views, commissions,
earnings, or affiliate links. If asked to do something not connected yet, explain
the limitation and give the next practical step. Keep answers direct and actionable.

Boss's message:
{message}
"""
    client = get_client()
    errors = []
    model = "gemini-3.8-flash"
    for attempt, delay in enumerate((0, 3, 8), start=1):
        try:
            if delay:
                import time
                time.sleep(delay)
            result = client.models.generate_content(model=model, contents=prompt)
            if result.text and result.text.strip():
                return {"reply": result.text.strip()}
            errors.append(f"{model}: empty response")
        except Exception as exc:
            errors.append(f"{model} attempt {attempt}: {str(exc)[:160]}")

    print("Gemini chat errors:", " | ".join(errors))
    raise HTTPException(
        status_code=502,
        detail="AI service could not answer. Check the server logs and Gemini API key."
    )
