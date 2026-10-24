import os
import time
import threading
import hashlib
import json
import requests
from typing import Any, Dict

# Load configuration from config.py (environment variables already loaded)
from config import GEMMA_MODEL_FAST, GEMMA_MODEL_DEEP, MIN_SECONDS_BETWEEN_CALLS

# Rate‑limiter shared across calls
_rate_lock = threading.Lock()
_last_call_ts = 0.0

def _enforce_rate_limit() -> None:
    """Enforce the minimum interval between API calls.
    Uses the MIN_SECONDS_BETWEEN_CALLS value from config.
    """
    global _last_call_ts
    with _rate_lock:
        now = time.time()
        elapsed = now - _last_call_ts
        wait = MIN_SECONDS_BETWEEN_CALLS - elapsed
        if wait > 0:
            time.sleep(wait)
        _last_call_ts = time.time()

def _post_gemini(model_name: str, prompt: str, system: str) -> Dict[str, Any]:
    """Call the Gemini REST endpoint.

    Parameters
    ----------
    model_name: str
        Full model identifier (e.g. "gemma-4-26b-a4b-it").
    prompt: str
        The user supplied text.
    system: str
        System instruction that drives language and thinking mode.

    Returns
    -------
    dict
        Parsed JSON response from the API.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY in environment")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": system}]},
    }
    response = requests.post(url, headers=headers, data=json.dumps(body), timeout=30)
    if not response.ok:
        # Raise with status and body for retry handling
        raise RuntimeError(f"Gemini API error {response.status_code}: {response.text}")
    return response.json()

def _extract_text_from_response(resp_json: Dict[str, Any]) -> str:
    """Extract the main textual response from the Gemini JSON payload.
    Concatenates all ``text`` parts of the first candidate, skipping any part that
    has a ``thought`` flag (Gemini may include auxiliary information)."""
    try:
        candidate = resp_json.get("candidates", [])[0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        texts = []
        for part in parts:
            # Skip parts that are marked as a thought or have a non‑text payload
            if part.get("text") and not part.get("thought"):
                texts.append(part["text"])
        return "\n".join(texts).strip()
    except Exception as e:
        raise RuntimeError(f"Unable to parse Gemini response: {e}")

def call_model(prompt: str, mode: str = "fast", language: str = "English", thinking: str = "minimal") -> Dict[str, Any]:
    """High‑level wrapper used by the UI.

    Parameters
    ----------
    prompt: str – the (redacted) log or incident description.
    mode: "fast" or "deep" – selects which Gemma model to use.
    language: UI language (English or Roman Urdu) – added to the system prompt.
    thinking: "minimal" or "high" – also added to the system prompt.

    Returns
    -------
    dict with keys:
        * ``output`` – the model's text response.
        * ``model`` – model name actually used.
        * ``latency_ms``
        * ``retries``
        * ``cached`` – always False here.
    """
    primary = GEMMA_MODEL_FAST if mode == "fast" else GEMMA_MODEL_DEEP
    fallback = GEMMA_MODEL_DEEP if mode == "fast" else GEMMA_MODEL_FAST
    system_prompt = f"You are an incident‑analysis assistant. Respond in {language}. Use {thinking} thinking."
    attempts = 0
    max_retries = 2
    backoff = 1.0
    model_used = primary
    while attempts <= max_retries:
        attempts += 1
        try:
            _enforce_rate_limit()
            start = time.time()
            resp_json = _post_gemini(model_used, prompt, system_prompt)
            latency = (time.time() - start) * 1000
            output_text = _extract_text_from_response(resp_json)
            return {
                "output": output_text,
                "model": model_used,
                "latency_ms": latency,
                "retries": attempts - 1,
                "cached": False,
            }
        except RuntimeError as e:
            err_msg = str(e)
            # Retry on rate‑limit or server errors
            if any(code in err_msg for code in ["429", "503", "rate", "timed out"]):
                if attempts <= max_retries:
                    time.sleep(backoff + (0.5 * attempts))
                    backoff *= 2
                    continue
            # Fallback model on invalid‑model errors
            if "Invalid model" in err_msg or "model" in err_msg.lower():
                if model_used != fallback:
                    model_used = fallback
                    continue
            # Unrecoverable error – return with details
            return {
                "output": f"Error: {err_msg}",
                "model": model_used,
                "latency_ms": None,
                "retries": attempts - 1,
                "cached": False,
            }
    # Exhausted retries
    return {
        "output": "Error: exhausted retries",
        "model": model_used,
        "latency_ms": None,
        "retries": attempts - 1,
        "cached": False,
    }

# Simple in‑memory cache (keyed by SHA256 of prompt+mode+language)
_cache_store: Dict[str, Dict[str, Any]] = {}
_cache_lock = threading.Lock()

def cached_call(prompt: str, mode: str, language: str) -> Dict[str, Any]:
    """Cached wrapper around :func:`call_model`.
    The cache key includes the prompt, selected mode and language.
    """
    key_raw = f"{prompt}\n{mode}\n{language}".encode("utf-8")
    key = hashlib.sha256(key_raw).hexdigest()
    with _cache_lock:
        if key in _cache_store:
            cached = _cache_store[key].copy()
            cached["cached"] = True
            return cached
    result = call_model(prompt, mode=mode, language=language)
    with cache_lock:
        _cache_store[key] = result.copy()
    return result
