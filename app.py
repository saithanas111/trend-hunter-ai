
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai

app = FastAPI(title="Trend Hunter AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

def get_client():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY secret is not configured."
        )
    return genai.Client(api_key=key)

class ChatRequest(BaseModel):
    message: str

@app.get("/")
def home():
    return {"status": "online", "agent": "Trend Hunter AI"}

@app.post("/chat")
def chat(request: ChatRequest):
    message = request.message.strip()

    if not message:
        raise HTTPException(status_code=400, detail="Message is empty.")
    if len(message) > 4000:
        raise HTTPException(status_code=400, detail="Message is too long.")

    prompt = f"""
You are Trend Hunter AI, the business assistant for Trending Finds.
Address the user as Boss.
Understand the user's instructions and give practical, honest answers.
Never claim you completed an action unless a connected tool confirms it.
Never invent live trends, product statistics, orders, views, or affiliate links.
If you cannot perform an action yet, explain what integration is needed
and give the next practical step.
The user may communicate in Urdu, Roman Urdu, or English.
Reply in the language the user uses.

User message:
{message}
"""

    client = get_client()
    errors = []

    for model in ["gemini-3.6-flash", "gemini-3.5-flash"]:
        try:
            result = client.models.generate_content(
                model=model,
                contents=prompt
            )
            if result.text:
                return {"reply": result.text}
        except Exception as exc:
            errors.append(f"{model}: {str(exc)[:200]}")

    raise HTTPException(
        status_code=502,
        detail="AI service could not answer. Please try again later."
        )
          
