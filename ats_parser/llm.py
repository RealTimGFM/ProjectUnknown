from typing import List
import os, json, requests
from .models import ExperienceItem, DateSpan

USE_LLM = os.getenv("USE_LLM", "0") == "1"


def extract_experience_llm(text: str) -> List[ExperienceItem]:
    """
    LLM extractor for EXPERIENCE.
    - Requires USE_LLM=1 and OPENAI_API_KEY.
    - Enforces a JSON *array* via json_schema.
    """
    if not USE_LLM or not (text or "").strip():
        return []
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return []

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    schema = {
        "name": "experience_array",
        "schema": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "location": {"type": "string"},
                    "dates": {
                        "type": "object",
                        "properties": {
                            "start": {"type": ["string", "null"]},
                            "end": {"type": ["string", "null"]},
                            "months": {"type": ["integer", "null"]},
                        },
                    },
                    "bullets": {"type": "array", "items": {"type": "string"}},
                    "technologies": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number"},
                },
                "required": ["title", "company", "dates", "bullets"],
            },
        },
        "strict": True,
    }

    prompt = f"""Extract the candidate's work EXPERIENCE from the text.
Return a JSON array. Dates must be YYYY-MM or null. If end date is current, set end to "Present".
Text:
{text}
"""

    try:
        r = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "input": prompt,
                "response_format": {"type": "json_schema", "json_schema": schema},
                "max_output_tokens": 2000,
            },
            timeout=45,
        )
        data = r.json()
        # Responses API (preferred)
        out_text = ""
        try:
            out_text = data["output"][0]["content"][0]["text"]
        except Exception:
            # Chat-style fallback
            out_text = (
                data.get("choices", [{}])[0].get("message", {}).get("content", "")
            )

        arr = json.loads(out_text) if out_text else []
        if not isinstance(arr, list):
            return []
        out: List[ExperienceItem] = []
        for it in arr:
            out.append(
                ExperienceItem(
                    title=it.get("title", ""),
                    company=it.get("company", ""),
                    location=it.get("location", ""),
                    dates=DateSpan(**(it.get("dates") or {})),
                    bullets=it.get("bullets") or [],
                    technologies=it.get("technologies") or [],
                    confidence=float(it.get("confidence") or 0.8),
                )
            )
        return out
    except Exception:
        return []
