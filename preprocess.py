import re
from typing import Tuple, Dict
from config import MAX_LOG_CHARS

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)

def dedupe_lines(text: str) -> str:
    lines = text.splitlines()
    result = []
    i = 0
    while i < len(lines):
        # check for repetition of the same line
        count = 1
        while i + count < len(lines) and lines[i + count] == lines[i]:
            count += 1
        if count > 1:
            result.append(f"{lines[i]} (x{count})")
            i += count
        else:
            result.append(lines[i])
            i += 1
    return "\n".join(result)

_ERROR_REGEX = re.compile(r"(?i)error|fail|fatal|exception|denied|killed|exit code|panic|traceback|refused|timeout|not found")

def extract_error_windows(text: str, window: int = 8) -> str:
    lines = text.splitlines()
    indices = [i for i, l in enumerate(lines) if _ERROR_REGEX.search(l)]
    if not indices:
        return ""
    keep = set()
    for idx in indices:
        start = max(0, idx - window)
        end = min(len(lines), idx + window + 1)
        keep.update(range(start, end))
    return "\n".join(lines[i] for i in sorted(keep))

def truncate(text: str, limit: int = MAX_LOG_CHARS) -> str:
    if len(text) <= limit:
        return text
    # keep head and tail, split roughly half
    head_len = limit // 2 - 50
    tail_len = limit // 2 - 50
    head = text[:head_len]
    tail = text[-tail_len:]
    return f"{head}\n... [truncated] ...\n{tail}"

def preprocess_log(raw_text: str) -> Tuple[str, Dict[str, float]]:
    """Run full preprocessing pipeline.

    Returns the processed log and a dict of statistics:
        - original_chars
        - reduced_chars
        - reduction_pct
    """
    original = raw_text
    cleaned = strip_ansi(original)
    cleaned = dedupe_lines(cleaned)
    windowed = extract_error_windows(cleaned)
    reduced = truncate(windowed, MAX_LOG_CHARS)
    stats = {
        "original_chars": len(original),
        "reduced_chars": len(reduced),
        "reduction_pct": round(100 * (1 - len(reduced) / len(original)), 2) if len(original) > 0 else 0,
    }
    return reduced, stats
