import requests

from app.config import OLLAMA_MODEL, OLLAMA_URL, USE_LLM

_available = None


def llm_available():
    global _available
    if not USE_LLM:
        return False
    if _available is None:
        try:
            r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
            _available = r.status_code == 200
        except requests.RequestException:
            _available = False
    return _available


def generate(prompt, system="You are a helpful industrial customer support agent.", max_tokens=400):
    if not llm_available():
        return None
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": max_tokens},
            },
            timeout=90,
        )
        r.raise_for_status()
        text = r.json().get("response", "").strip()
        return text or None
    except requests.RequestException:
        return None
