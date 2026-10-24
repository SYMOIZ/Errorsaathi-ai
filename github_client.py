import os
import re
import json
import base64
from typing import Dict, List, Any, Optional
import requests
from urllib.parse import urlparse

# GitHub API helper – uses a personal access token from .env or Streamlit secrets
try:
    import streamlit as st
except Exception:
    st = None

_GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or (st.secrets.get("GITHUB_TOKEN") if st else None)

_API_BASE = "https://api.github.com"

def _auth_headers() -> Dict[str, str]:
    if not _GITHUB_TOKEN:
        raise RuntimeError("Missing GITHUB_TOKEN in environment")
    return {"Authorization": f"token {_GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}

def parse_pr_url(pr_url: str) -> Optional[Dict[str, str]]:
    """Extract owner, repo, and PR number from a GitHub PR URL.
    Returns ``{"owner": ..., "repo": ..., "pr": ...}`` or ``None`` if invalid.
    """
    try:
        parsed = urlparse(pr_url)
        if parsed.netloc not in {"github.com", "www.github.com"}:
            return None
        # Expected path: /owner/repo/pull/123
        parts = [p for p in parsed.path.split('/') if p]
        if len(parts) >= 4 and parts[2] == "pull":
            return {"owner": parts[0], "repo": parts[1], "pr": parts[3]}
        return None
    except Exception:
        return None

def get_pr_details(owner: str, repo: str, pr_number: str) -> Dict[str, Any]:
    """Return PR title, author login, head SHA and other useful fields."""
    url = f"{_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"
    resp = requests.get(url, headers=_auth_headers())
    if resp.status_code == 404:
        raise RuntimeError("PR not found or repository is private")
    if resp.status_code == 401:
        raise RuntimeError("Invalid or missing GitHub token")
    resp.raise_for_status()
    data = resp.json()
    return {
        "title": data.get("title"),
        "author": data.get("user", {}).get("login"),
        "head_sha": data.get("head", {}).get("sha"),
        "url": data.get("html_url"),
    }

def list_workflow_runs(owner: str, repo: str, sha: str) -> List[Dict[str, Any]]:
    """List workflow runs for a given commit SHA. Returns list of run dicts."""
    url = f"{_API_BASE}/repos/{owner}/{repo}/actions/runs?sha={sha}"
    resp = requests.get(url, headers=_auth_headers())
    resp.raise_for_status()
    runs = resp.json().get("workflow_runs", [])
    return runs

def list_failed_jobs(owner: str, repo: str, run_id: int) -> List[Dict[str, Any]]:
    """List jobs for a workflow run and return only those with conclusion='failure'."""
    url = f"{_API_BASE}/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
    resp = requests.get(url, headers=_auth_headers())
    resp.raise_for_status()
    jobs = resp.json().get("jobs", [])
    failed = [job for job in jobs if job.get("conclusion") == "failure"]
    return failed

def download_job_log(owner: str, repo: str, job_id: int) -> str:
    """Download raw log text for a job. Returns the log as a string.
    GitHub returns a gzipped log; we decode it.
    """
    url = f"{_API_BASE}/repos/{owner}/{repo}/actions/jobs/{job_id}/logs"
    resp = requests.get(url, headers=_auth_headers())
    resp.raise_for_status()
    # The response is a binary zip. GitHub actually returns a .zip of logs.
    # For simplicity we attempt to read as text; many logs are plain.
    # If the payload is zip, we extract the first file.
    if resp.headers.get("Content-Type", "").startswith("application/zip"):
        import zipfile, io
        zip_bytes = io.BytesIO(resp.content)
        with zipfile.ZipFile(zip_bytes) as zf:
            # Usually there is a single file named "log.txt"
            name = zf.namelist()[0]
            return zf.read(name).decode(errors="replace")
    else:
        return resp.text

def get_pr_diff(owner: str, repo: str, pr_number: str, max_chars: int = 12000) -> str:
    """Fetch the unified diff for a PR via the compare endpoint.
    Truncate to ``max_chars`` to avoid huge payloads.
    """
    # First get the PR details to know base and head refs
    url = f"{_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}" 
    pr = requests.get(url, headers=_auth_headers()).json()
    base = pr.get("base", {}).get("sha")
    head = pr.get("head", {}).get("sha")
    if not base or not head:
        raise RuntimeError("Unable to determine base/head SHAs for diff")
    compare_url = f"{_API_BASE}/repos/{owner}/{repo}/compare/{base}...{head}"
    resp = requests.get(compare_url, headers=_auth_headers())
    resp.raise_for_status()
    patch = resp.json().get("files", [])
    diff_parts = []
    for f in patch:
        # ``patch`` field contains the unified diff for the file
        diff = f.get("patch")
        if diff:
            diff_parts.append(diff)
    full_diff = "\n".join(diff_parts)
    if len(full_diff) > max_chars:
        return full_diff[:max_chars] + "... (truncated)"
    return full_diff

def post_pr_comment(owner: str, repo: str, pr_number: str, comment_body: str) -> Dict[str, Any]:
    """Create a comment on the PR (issues API works for PRs)."""
    url = f"{_API_BASE}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    resp = requests.post(url, headers=_auth_headers(), json={"body": comment_body})
    resp.raise_for_status()
    return resp.json()

# Helper to aggregate failed logs and diff into a single payload for the pipeline
def fetch_pr_context(pr_url: str) -> Dict[str, Any]:
    info = parse_pr_url(pr_url)
    if not info:
        raise RuntimeError("Invalid GitHub PR URL")
    owner, repo, pr = info["owner"], info["repo"], info["pr"]
    pr_details = get_pr_details(owner, repo, pr)
    head_sha = pr_details["head_sha"]
    # Get workflow runs for that SHA and find the latest run
    runs = list_workflow_runs(owner, repo, head_sha)
    if not runs:
        raise RuntimeError("No workflow runs found for this commit")
    # Choose the most recent run (assumes sorted by created_at desc)
    run = runs[0]
    run_id = run.get("id")
    failed_jobs = list_failed_jobs(owner, repo, run_id)
    if not failed_jobs:
        raise RuntimeError("No failed jobs found in the latest workflow run")
    logs = []
    job_names = []
    for job in failed_jobs:
        job_id = job.get("id")
        job_name = job.get("name")
        try:
            log_text = download_job_log(owner, repo, job_id)
            logs.append(log_text)
            job_names.append(job_name)
        except Exception as e:
            logs.append(f"<failed to fetch log for job {job_name}: {e}>")
            job_names.append(job_name)
    diff = get_pr_diff(owner, repo, pr)
    return {
        "pr_title": pr_details["title"],
        "pr_author": pr_details["author"],
        "failed_job_names": job_names,
        "failed_logs": logs,
        "pr_diff": diff,
        "pr_number": pr,
        "owner": owner,
        "repo": repo,
    }
