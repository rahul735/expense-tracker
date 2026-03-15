"""
AI Parser abstraction layer.
Supports multiple providers: Gemini, Claude, OpenAI.
Each provider parses a natural language expense string into structured data.
"""

import json
import re
from datetime import datetime, timedelta


def parse_expense_text(text: str, provider: str, api_key: str) -> dict:
    """
    Route to the correct AI provider and return structured expense data.
    Returns: { date, category, description, amount, currency, error }
    """
    provider = provider.lower()
    if provider == "gemini":
        return _parse_with_gemini(text, api_key)
    elif provider == "claude":
        return _parse_with_claude(text, api_key)
    elif provider == "openai":
        return _parse_with_openai(text, api_key)
    else:
        return {"error": f"Unknown provider: {provider}"}


# ── Shared prompt ────────────────────────────────────────────────────────────

def _build_prompt(text: str) -> str:
    today = datetime.today().strftime("%Y-%m-%d")
    yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    return f"""Extract expense details from this sentence and return ONLY valid JSON.

Today's date is {today}. Yesterday was {yesterday}.

Sentence: "{text}"

Return this exact JSON structure (no extra text, no markdown):
{{
  "amount": <number>,
  "currency": "<INR or USD or EUR etc>",
  "category": "<one of: Food, Transport, Shopping, Entertainment, Health, Utilities, Other>",
  "description": "<short description>",
  "date": "<YYYY-MM-DD format>"
}}

Rules:
- If currency not mentioned, default to INR
- Map words like "food", "lunch", "dinner", "groceries" → Food
- Map "cab", "uber", "bus", "petrol", "fuel" → Transport
- Map "movie", "netflix", "game" → Entertainment
- Map "medicine", "doctor", "hospital" → Health
- Map "electricity", "internet", "rent", "water" → Utilities
- Map "clothes", "shoes", "amazon" → Shopping
- "yesterday" → {yesterday}, "today" → {today}
- If date not mentioned, use today ({today})"""


def _extract_json(text: str) -> dict:
    """Extract JSON from AI response, handling markdown code blocks."""
    text = text.strip()
    # Remove markdown code blocks if present
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse AI response as JSON: {e}. Response was: {text[:200]}"}


# ── Gemini ───────────────────────────────────────────────────────────────────

def _parse_with_gemini(text: str, api_key: str) -> dict:
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=_build_prompt(text)
        )
        return _extract_json(response.text)
    except ImportError:
        return {"error": "google-genai package not installed. Run: pip install google-genai"}
    except Exception as e:
        return {"error": str(e)}


# ── Claude ───────────────────────────────────────────────────────────────────

def _parse_with_claude(text: str, api_key: str) -> dict:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=256,
            messages=[{"role": "user", "content": _build_prompt(text)}]
        )
        return _extract_json(response.content[0].text)
    except ImportError:
        return {"error": "anthropic package not installed. Run: pip install anthropic"}
    except Exception as e:
        return {"error": str(e)}


# ── OpenAI ───────────────────────────────────────────────────────────────────

def _parse_with_openai(text: str, api_key: str) -> dict:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": _build_prompt(text)}],
            max_tokens=256,
        )
        return _extract_json(response.choices[0].message.content)
    except ImportError:
        return {"error": "openai package not installed. Run: pip install openai"}
    except Exception as e:
        return {"error": str(e)}
