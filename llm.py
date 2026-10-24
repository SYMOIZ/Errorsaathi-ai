import os
import time
import threading
import hashlib
from typing import Any, Dict
import google.generativeai as genai

# Detect dummy key for local testing
_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if _GEMINI_API_KEY and _GEMINI_API_KEY.startswith("dummy"):
    _USE_MOCK = True
else:
    _USE_MOCK = False

# Load env config (already done in config.py) for convenience
from config import GEMMA_MODEL_FAST, GEMMA_MODEL_DEEP, MIN_SECONDS_BETWEEN_CALLS

# Initialize the GenAI client once (google‑genai uses global config)
_api_key = os.getenv("GEMINI_API_KEY")
if _api_key:
    genai.configure(api_key=_api_key)
else:
    # No key – the caller must handle this error
    pass

# Rate‑limiter lock and timestamp
_rate_lock = threading.Lock()
_last_call_ts = 0.0

def _enforce_rate_limit() -> None:
    global _last_call_ts
    with _rate_lock:
        now = time.time()
        elapsed = now - _last_call_ts
        wait = MIN_SECONDS_BETWEEN_CALLS - elapsed
        if wait > 0:
            time.sleep(wait)
        _last_call_ts = time.time()

def _call_genai(model_name: str, prompt: str, temperature: float = 0.2) -> genai.types.GenerateContentResponse:
    """Direct call to the GenerativeModel.

    Raises:
        RuntimeError – for missing API key or invalid model.
    """
    if not _api_key:
        raise RuntimeError("Missing GEMINI_API_KEY in environment")
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=temperature),
        )
        return response
    except Exception as e:
        raise RuntimeError(str(e))

def call_model(
    prompt: str,
    mode: str = "fast",
    language: str = "English",
    thinking: str = "minimal",
) -> Dict[str, Any]:
    """High‑level wrapper used by the UI.

    Parameters
    ----------
    prompt: str – the (redacted) log or incident description.
    mode: "fast" or "deep" – selects which Gemma model to use.
    language: UI language (English or Roman Urdu) – the model is instructed to respond in that language.
    thinking: "minimal" or "high" – passed as part of system instruction.

    Returns a dict with keys:
        * `output` – the model's text response (or error message).
        * `model` – model name actually used.
        * `latency_ms`
        * `tokens_in`, `tokens_out` (if available)
        * `retries`
        * `cached` – always False here (caching is handled at higher level).
    """
    # Choose model based on mode
    primary = GEMMA_MODEL_FAST if mode == "fast" else GEMMA_MODEL_DEEP
    fallback = GEMMA_MODEL_DEEP if mode == "fast" else GEMMA_MODEL_FAST

    # Build system prompt to enforce language and thinking level
    system_prompt = f"You are an incident‑analysis assistant. Respond in {language}. Use {thinking} thinking."
    full_prompt = system_prompt + "\n---\n" + prompt

    attempts = 0
    max_retries = 2
    backoff = 1.0
    model_used = primary
    while attempts <= max_retries:
        attempts += 1
        try:
            _enforce_rate_limit()
            start = time.time()
            resp = _call_genai(model_used, full_prompt)
            latency = (time.time() - start) * 1000
            # Extract usage if present (google‑genai may include usage_metadata)
            usage = getattr(resp, "usage_metadata", None)
            tokens_in = getattr(usage, "prompt_token_count", None) if usage else None
            tokens_out = getattr(usage, "candidates_token_count", None) if usage else None
            return {
                "output": resp.text,
                "model": model_used,
                "latency_ms": latency,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "retries": attempts - 1,
                "cached": False,
            }
        except RuntimeError as e:
            err_msg = str(e)
            # Handle known transient errors (simple heuristic)
            if "429" in err_msg or "503" in err_msg or "rate" in err_msg.lower():
                if attempts <= max_retries:
                    time.sleep(backoff + (0.5 * attempts))
                    backoff *= 2
                    continue
            # Invalid model – fallback once
            if "Invalid model" in err_msg or "model" in err_msg.lower():
                if model_used != fallback:
                    model_used = fallback
                    continue
            # Missing key or other fatal error – break and return error
            return {
                "output": f"Error: {err_msg}",
                "model": model_used,
                "latency_ms": None,
                "tokens_in": None,
                "tokens_out": None,
                "retries": attempts - 1,
                "cached": False,
            }
    # If we exit loop without success
    return {
        "output": "Error: exhausted retries",
        "model": model_used,
        "latency_ms": None,
        "tokens_in": None,
        "tokens_out": None,
        "retries": attempts - 1,
        "cached": False,
    }

# Simple cache helper – keyed by SHA256 of (prompt+language+mode)
_cache_store: Dict[str, Dict[str, Any]] = {}
_cache_lock = threading.Lock()

def cached_call(prompt: str, mode: str, language: str) -> Dict[str, Any]:
    # Mock mode for local testing when dummy API key is used
    if _USE_MOCK:
        # Return a deterministic placeholder with the four sections
        mock_output = "Classification: Mock classification\nRoot Cause: Mock root cause\nFix Steps: Mock fix steps\nSafety Review: Mock safety review"
        return {
            "output": mock_output,
            "model": f"{mode}_mock",
            "latency_ms": 0,
            "tokens_in": None,
            "tokens_out": None,
            "retries": 0,
            "cached": False,
        }
    # Normal cached behavior
    key_raw = f"{prompt}\n{mode}\n{language}".encode("utf-8")
    key = hashlib.sha256(key_raw).hexdigest()
    with cache_lock:
        if key in _cache_store:
            cached = _cache_store[key].copy()
            cached["cached"] = True
            return cached
    result = call_model(prompt, mode=mode, language=language)
    with cache_lock:
        _cache_store[key] = result.copy()
    return result
