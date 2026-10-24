import json
from typing import List, Dict, Any
import re
import llm

def _build_prompt(logs: List[str], diff: str) -> str:
    """Construct a prompt for the LLM.
    The LLM is asked to analyze the failed CI job logs and the PR diff,
    and return a JSON object with the following keys:
        - file: the filename that likely caused the failure
        - line: the line number (int) within that file
        - explanation: brief description of the issue
        - patch: a minimal unified‑diff snippet fixing the problem
    If the LLM cannot pinpoint a location it should set ``file`` and ``line`` to ``null``.
    """
    log_text = "\n".join(logs) if isinstance(logs, list) else str(logs)
    prompt = (
        "You are an expert developer tasked with pinpointing the exact file and line in a PR that caused a CI failure. "
        "Given the failed job log and the PR diff, identify the most likely source of the error and provide a minimal fix. "
        "Return ONLY a JSON object (no surrounding text) with the keys: file, line, explanation, patch. "
        "If you cannot determine a concrete location, set file and line to null and explain why. "
        "\n\n--- FAILED LOG ---\n" + log_text + "\n\n--- PR DIFF ---\n" + diff
    )
    return prompt

def blame_agent(log: List[str], diff: str) -> Dict[str, Any]:
    """Call Gemma 4 to analyse CI failure and produce a blame result.

    Parameters
    ----------
    log: List[str]
        List of failed job log strings.
    diff: str
        Unified diff for the PR.

    Returns
    -------
    dict with keys ``file``, ``line``, ``explanation`` and ``suggested_patch``.
    Raises ``RuntimeError`` on LLM call or JSON parsing failures.
    """
    prompt = _build_prompt(log, diff)
    # Use the fast model for quick analysis; fallback handled inside llm.
    result = llm.call_model(prompt=prompt, mode="fast", language="English")
    if result.get("output", "").startswith("Error:"):
        raise RuntimeError(f"LLM error during blame analysis: {result['output']}")
    output_text = result.get("output", "").strip()
    try:
        data = json.loads(output_text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse Blame Agent JSON response: {e}. Raw output: {output_text}")
    required = {"file", "line", "explanation", "patch"}
    if not required.issubset(data.keys()):
        raise RuntimeError(f"Blame Agent response missing keys. Received: {list(data.keys())}")
    return {
        "file": data["file"],
        "line": data["line"],
        "explanation": data["explanation"],
        "suggested_patch": data["patch"],
    }

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
