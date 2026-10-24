import os
import streamlit as st
from dotenv import load_dotenv

# Load .env file (will be ignored if absent)
load_dotenv()

# Environment variables (filled from .env or Streamlit secrets)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
GEMMA_MODEL_FAST = os.getenv("GEMMA_MODEL_FAST", "gemma-4-26b-a4b-it") or st.secrets.get("GEMMA_MODEL_FAST")
GEMMA_MODEL_DEEP = os.getenv("GEMMA_MODEL_DEEP", "gemma-4-31b-it") or st.secrets.get("GEMMA_MODEL_DEEP")
MAX_LOG_CHARS = int(os.getenv("MAX_LOG_CHARS", "12000")) or int(st.secrets.get("MAX_LOG_CHARS", 12000))
MIN_SECONDS_BETWEEN_CALLS = float(os.getenv("MIN_SECONDS_BETWEEN_CALLS", "1.5")) or float(st.secrets.get("MIN_SECONDS_BETWEEN_CALLS", 1.5))

# UI constants
LANGUAGES = ["English", "Roman Urdu"]
DEFAULT_LANGUAGE = "English"
MODES = ["Auto", "Fast", "Deep"]
DEFAULT_MODE = "Auto"
