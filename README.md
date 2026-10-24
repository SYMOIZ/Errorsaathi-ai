# 🩺 ErrorSaathi — CI Doctor for Open-Source Contributors

> Diagnose failed CI runs and DevOps errors in **English or Roman Urdu**, powered by **Google Gemma 4**.

[![License: MIT](https://img.shields.io/badge/License-MIT-teal.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-red)
![Gemma 4](https://img.shields.io/badge/Model-Gemma%204-orange)

Built at **Hacktoberfest 2026 · Karachi Hack Day** (Disrupt PECHS · AWS User Group Karachi · MLH · DEV) — **Harness track**.

---

## The problem

Every Hacktoberfest, many first-time contributors open a pull request, see a red ❌ on CI, and give up.
CI logs are long, noisy and cryptic, documentation is mostly in English, and maintainers spend time
explaining the same failures again and again.

## The solution

ErrorSaathi takes a **GitHub PR URL** (or a pasted log, log file, or error screenshot), pulls the failed
CI job logs and the PR diff, and uses **Gemma 4** to explain:

- **What** failed and how severe it is
- **Why** it most likely failed (facts vs. hypotheses, with confidence)
- **Which changed file/line** probably caused it
- **How** to fix it — step by step, with every command labelled **SAFE / CAUTION / DESTRUCTIVE**

…in **English or Roman Urdu**, so junior engineers and new contributors can understand it.
The diagnosis can then be posted back to the PR as a comment — **only after the user previews and confirms it**.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔗 **GitHub PR input** | Paste a PR URL → fetches PR details, failed workflow jobs, job logs and the diff via the GitHub API |
| 📋 **Multiple inputs** | Paste a log, upload a `.log`/`.txt` file, or upload a screenshot of an error |
| 🔒 **Secret redaction** | AWS keys, tokens, passwords, private keys, connection strings and emails are masked **before** anything is sent to the model |
| ⚡ **Log preprocessing** | Strips ANSI codes, collapses repeated lines, keeps the lines around errors and truncates long logs to save tokens |
| 🧭 **Rule-based router** | Regex-based, zero-cost pre-classification chooses a fast (single-call) or deep (multi-agent) path |
| 🤖 **Multi-agent analysis** | Triage → Investigator → Fixer → Safety Reviewer, plus a Blame Agent for PR diffs |
| 🛡️ **Safety first** | The app **never executes commands** or changes infrastructure; risky commands are flagged |
| 🌐 **Bilingual output** | English or Roman Urdu explanations (commands and code stay in English) |
| 💬 **PR comment** | Preview the diagnosis, then post it to the PR only after explicit confirmation |

---

## 🧠 How Gemma 4 is used

Gemma 4 does the core reasoning in ErrorSaathi:

| Model | Used for |
|---|---|
| `gemma-4-26b-a4b-it` (MoE, faster) | Fast mode, triage, fix steps |
| `gemma-4-31b-it` (dense, stronger reasoning) | Deep investigation and safety review |

Gemma 4 capabilities used or designed for:
- **System instructions** — a specialised role prompt for each agent
- **Multi-step reasoning** — root‑cause analysis separating facts from hypotheses
- **Image understanding** — extracting error text from screenshots
- **Function calling** — local, deterministic helper tools (exit codes, HTTP codes, Kubernetes reasons)
- **Multilingual output** — Roman Urdu explanations

---

## 🏗️ Architecture

```mermaid
flowchart LR
    A[GitHub PR URL / Log / File / Screenshot] --> B[GitHub API<br/>failed job logs + diff]
    A --> C
    B --> C[Preprocess<br/>clean · dedupe · error windows]
    C --> D[Redact secrets]
    D --> E[Router<br/>regex, no API call]
    E -->|simple| F[Fast mode<br/>1 Gemma call]
    E -->|complex| G[Triage Agent]
    G --> H[Investigator Agent]
    H --> I[Fixer Agent]
    I --> J[Safety Reviewer]
    A -->|PR| K[Blame Agent<br/>error → file/line]
    F --> L[Diagnosis + Runbook]
    J --> L
    K --> L
    L --> M[Preview → Confirm → PR comment]
```

### Project structure

```
app.py            Streamlit UI
config.py         Environment / Streamlit secrets loading
llm.py            Gemma 4 client wrapper (retries, rate limit, fallback)
agents.py         Agent prompts and logic (incl. Blame Agent)
preprocess.py     Log cleaning, dedupe, error-window extraction, truncation
redact.py         Secret redaction
github_client.py  GitHub API: PR info, failed jobs, logs, diff, PR comments
requirements.txt  Python dependencies
.env.example      Environment variable template (no real secrets)
```

---

## 🚀 Getting started

### 1. Prerequisites
- Python **3.10 – 3.13**
- A **Gemini API key** from [Google AI Studio](https://aistudio.google.com/)
- A **GitHub fine‑grained token** (read: Actions, Contents, Pull requests · write: Pull requests — only needed to post comments)

### 2. Install

```bash
git clone https://github.com/SYMOIZ/Errorsaathi-ai.git
cd Errorsaathi-ai
python -m venv .venv
# Windows (Git Bash):  source .venv/Scripts/activate
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# macOS/Linux:          source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure secrets

Create `.streamlit/secrets.toml` (already git‑ignored):

```toml
GEMINI_API_KEY = "your_gemini_key"
GITHUB_TOKEN = "your_github_token"
GEMMA_MODEL_FAST = "gemma-4-26b-a4b-it"
GEMMA_MODEL_DEEP = "gemma-4-31b-it"
```

Or copy `.env.example` to `.env` and fill in the same values.

> ⚠️ Never commit real keys. `.env` and `.streamlit/secrets.toml` are listed in `.gitignore`.

### 4. Run

```bash
python -m streamlit run app.py
```

Open http://localhost:8501.

### 5. Deploy (optional)
Deploy on [Streamlit Community Cloud](https://share.streamlit.io): select this repo, set `app.py` as the
main file, and paste the values above into **Advanced settings → Secrets**.

---

## 🧪 Try it

**Paste log** tab → paste:

```
Error from server: pod/api-7d9f crashed. Back‑off restarting failed container
Last State: Terminated  Reason: OOMKilled  Exit Code: 137
AWS_ACCESS_KEY_ID=AKIAABCDEFGHIJKLMNOP
```

You should see the secret redacted and a diagnosis explaining the out‑of‑memory kill (exit code 137).

**GitHub PR URL** tab → paste a PR whose CI checks failed, e.g. `https://github.com/OWNER/REPO/pull/NUMBER`,
then click **Fetch PR** and **Analyze**.

> Please only post diagnosis comments on PRs you own or have permission to comment on.

---

## 🛡️ Safety & privacy design

- **Redaction before inference** — secrets are masked before any text reaches the model.
- **Advise‑only** — the app never runs generated commands or modifies infrastructure.
- **Risk labels** — commands are labelled SAFE / CAUTION / DESTRUCTIVE; destructive patterns
  (`rm -rf`, `kubectl delete`, `terraform destroy`, `docker system prune`, `chmod 777`, `--force`) are flagged.
- **Human in the loop** — PR comments are posted only after preview and explicit confirmation.
- **Honest uncertainty** — the model is asked to separate facts from hypotheses and state confidence.

---

## ⚠️ Current status & limitations

This project was built in a few hours at a hackathon. Being transparent:

- AI output can be wrong — always review suggestions before acting on them.
- Some features are early prototypes; the Blame Agent may not always locate the exact file/line.
- Very large logs are truncated, so some context may be lost.
- Free‑tier Gemini API quotas can limit how many analyses run per minute.
- Only public GitHub repositories (or repos your token can access) are supported.

## 🗺️ Roadmap

- [ ] Reliable Blame Agent with structured JSON output and suggested patches
- [ ] Google Search grounding for links to official documentation
- [ ] GitHub App / Action that comments automatically on failed PRs (opt‑in by maintainers)
- [ ] Support for GitLab CI pipelines
- [ ] Urdu script and more regional languages
- [ ] Metrics dashboard (latency, tokens, cache hits)

---

## 🤝 Contributing

Contributions are welcome — especially new log patterns, redaction rules and language support.

1. Fork the repo and create a branch: `git checkout -b feature/my-change`
2. Commit your changes and open a pull request against `main`
3. Never include real API keys or tokens in commits

## 📄 License

[MIT](LICENSE) © 2026 Syed Moiz

## 🙏 Acknowledgements

- **Google Gemma 4** and the Gemini API
- **Hacktoberfest 2026**, **MLH**, **DEV** and **DigitalOcean**
- **Disrupt** and **AWS User Group Karachi** for hosting Karachi Hack Day
