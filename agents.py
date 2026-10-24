import re
from typing import List, Dict, Any

def blame_agent(log: List[str], diff: str) -> Dict[str, Any]:
    """Very simple placeholder Blame Agent.
    It scans the `log` lines for a pattern like `File "path", line N` and attempts
    to match it against the diff to suggest a patch location.
    Returns a dict with keys:
        - file: filename inferred from the log
        - line: line number as int (or None)
        - suggested_patch: a dummy unified‑diff string (or empty)
    This placeholder satisfies the UI expectations until a full implementation
    is added in later phases.
    """
    # Join log lines for easier regex search
    log_text = "\n".join(log) if isinstance(log, list) else str(log)
    # Simple regex to capture file path and line number from typical Python tracebacks
    match = re.search(r'File "(?P<file>.+?)", line (?P<line>\d+)', log_text)
    file_path = match.group('file') if match else 'unknown_file.py'
    line_num = int(match.group('line')) if match else None
    # Construct a tiny placeholder patch – real logic would diff against `diff`
    suggested_patch = f"--- a/{file_path}\n+++ b/{file_path}\n@@ -{line_num or 1},0 +{line_num or 1} @@\n+# TODO: add fix based on analysis"
    return {
        "file": file_path,
        "line": line_num,
        "suggested_patch": suggested_patch,
    }
