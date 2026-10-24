import re
from typing import Tuple, List

# Regex patterns for various secrets
_PATTERNS = {
    "aws_access_key": r"AKIA[0-9A-Z]{16}",
    "aws_secret_key": r"(?i)aws_secret_access_key\s*=\s*([\w/+=]{40})",
    "bearer_token": r"Bearer\s+[A-Za-z0-9\-._~+/]+=*",
    "jwt_token": r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
    "password_pair": r"(?:password|pwd|secret)\s*=\s*[^\s]+",
    "github_token": r"ghp_[A-Za-z0-9]{36}",
    "gitlab_token": r"glpat-[A-Za-z0-9_-]{20,}",
    "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "private_key": r"-----BEGIN PRIVATE KEY-----[\s\S]+?-----END PRIVATE KEY-----",
    "connection_string": r"(?i)connection\s*string\s*=\s*[^\n]+",
}

def redact_text(text: str) -> Tuple[str, int, List[str]]:
    """Redact secrets from *text*.

    Returns a tuple of ``(redacted_text, total_matches, types_found)`` where
    *total_matches* is the number of secret occurrences replaced and
    *types_found* is a list of the pattern keys that were triggered.
    """
    redacted = text
    total = 0
    types_found: List[str] = []
    for name, pattern in _PATTERNS.items():
        matches = re.findall(pattern, redacted)
        if matches:
            total += len(matches)
            types_found.append(name)
            # Replace each match with a placeholder preserving length for readability
            placeholder = f"<{name.upper()}_REDACTED>"
            redacted = re.sub(pattern, placeholder, redacted)
    return redacted, total, types_found
