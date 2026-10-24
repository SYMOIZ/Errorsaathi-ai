import streamlit as st
from config import LANGUAGES, MODES, DEFAULT_LANGUAGE, DEFAULT_MODE, GEMINI_API_KEY
import llm
import github_client
import agents
from redact import redact_text

st.set_page_config(page_title="ErrorSaathi AI", layout="wide")

# Sidebar
st.sidebar.title("Settings")
language = st.sidebar.selectbox("Language", LANGUAGES, index=LANGUAGES.index(DEFAULT_LANGUAGE))
mode = st.sidebar.selectbox("Mode", MODES, index=MODES.index(DEFAULT_MODE))

# Session state init
if 'log_input' not in st.session_state:
    st.session_state.log_input = ""
if 'redacted' not in st.session_state:
    st.session_state.redacted = None
if 'redact_count' not in st.session_state:
    st.session_state.redact_count = 0
if 'redact_types' not in st.session_state:
    st.session_state.redact_types = []

# Input tabs
tab_pr, tab1, tab2, tab3 = st.tabs(["GitHub PR URL", "Paste log", "Upload file", "Upload screenshot"])
with tab_pr:
    pr_url = st.text_input("Enter GitHub PR URL", "")
    if st.button("Fetch PR"):
        if not pr_url:
            st.error("Please enter a PR URL.")
        else:
            try:
                pr_context = github_client.fetch_pr_context(pr_url)
                st.session_state.pr_context = pr_context
                st.success(f"Fetched PR: {pr_context['pr_title']} by {pr_context['pr_author']}")
                st.write("Failed jobs:")
                for name in pr_context['failed_job_names']:
                    st.write(f"- {name}")
            except Exception as e:
                st.error(f"Error fetching PR: {e}")

with tab1:
    st.session_state.log_input = st.text_area("Paste your log here", height=300, value=st.session_state.log_input)
    if st.button("Load Sample 1"):
        sample_path = "samples/docker_build_fail.log"
        try:
            with open(sample_path, "r", encoding="utf-8") as f:
                st.session_state.log_input = f.read()
        except FileNotFoundError:
            st.warning(f"Sample file not found at {sample_path}. Please ensure the file exists or paste your log manually.")
with tab2:
    uploaded = st.file_uploader("Choose a .log or .txt file", type=["log", "txt"])
    if uploaded is not None:
        st.session_state.log_input = uploaded.getvalue().decode("utf-8")
        st.success("File loaded")
with tab3:
    img = st.file_uploader("Upload screenshot (png/jpg)", type=["png", "jpg", "jpeg"])
    if img is not None:
        st.warning("Screenshot handling will be added in later phases.")

# Redaction (only if not using PR context)
if not st.session_state.get('pr_context') and st.session_state.log_input:
    redacted_text, count, types_found = redact_text(st.session_state.log_input)
    st.session_state.redacted = redacted_text
    st.session_state.redact_count = count
    st.session_state.redact_types = types_found
    st.success(f"🔒 {count} secrets redacted")
    st.write(redacted_text[:1000] + ("..." if len(redacted_text) > 1000 else ""))

# If PR context is available, prepare combined log
if st.session_state.get('pr_context'):
    # Build combined log from failed logs and diff for analysis
    combined_log = "\n---FAILED LOGS---\n" + "\n".join(st.session_state.pr_context['failed_logs']) + "\n---DIFF---\n" + st.session_state.pr_context['pr_diff']
    # Redact any secrets in the combined payload
    redacted_text, count, types_found = redact_text(combined_log)
    st.session_state.redacted = redacted_text
    st.session_state.redact_count = count
    st.session_state.redact_types = types_found
    st.success(f"🔒 {count} secrets redacted from PR data")
    st.write(redacted_text[:1000] + ("..." if len(redacted_text) > 1000 else ""))



# Placeholder for analysis button (future phases)
if st.button("Analyze"):
    if not GEMINI_API_KEY:
        st.error("Missing GEMINI_API_KEY. Please set it in .env.")
        st.stop()
    if not st.session_state.redacted:
        st.warning("No log to analyze. Please provide input.")
        st.stop()
    try:
        # Call fast Gemma model via cached wrapper
        result = llm.cached_call(
            prompt=st.session_state.redacted,
            mode="fast",
            language=language,
        )
        if result.get("cached"):
            st.success("⚡ cache hit")
        if result.get("output", "").startswith("Error:"):
            st.error(result["output"])
        elif not result.get("output"):
            st.error("Model returned empty response.")
        else:
            output = result["output"]
            # Simple split on headings
            sections = {"Classification": "", "Root Cause": "", "Fix Steps": "", "Safety Review": ""}
            current = None
            for line in output.splitlines():
                hdr = line.strip().rstrip(":")
                if hdr in sections:
                    current = hdr
                    continue
                if current:
                    sections[current] += line + "\n"
            for title, body in sections.items():
                st.subheader(title)
                st.write(body.strip() or "(no content)")
            # Show metrics
            st.caption(f"Model: {result.get('model')} | Latency: {result.get('latency_ms', 0):.0f} ms")
            # Store analysis output for later use
            st.session_state.analysis_output = output
    except Exception as e:
        st.error(f"Unexpected error during analysis: {e}")

# Blame Agent button (only when PR context is present)
if st.session_state.get('pr_context'):
    if st.button("Run Blame Agent"):
        try:
            blame_info = agents.blame_agent(
                log=st.session_state.pr_context['failed_logs'],
                diff=st.session_state.pr_context['pr_diff']
            )
            st.session_state.blame_info = blame_info
            st.success("Blame analysis completed")
            st.subheader("Blame Result")
            st.write(f"File: {blame_info.get('file')}, Line: {blame_info.get('line')}")
            st.code(blame_info.get('suggested_patch'))
        except Exception as e:
            st.error(f"Blame Agent error: {e}")

    # PR comment posting UI
    if st.session_state.get('analysis_output'):
        comment_preview = f"**Summary**\n{st.session_state.analysis_output}\n\n**Suggested Patch**\n```\n{st.session_state.blame_info.get('suggested_patch') if st.session_state.get('blame_info') else 'N/A'}\n```\n---\n🤖 ErrorSaathi · Powered by Gemma 4"
        if st.button("Preview PR Comment"):
            st.subheader("Comment Preview")
            st.write(comment_preview)
            if st.button("Confirm & Post Comment"):
                try:
                    pr = st.session_state.pr_context
                    github_client.post_pr_comment(
                        owner=pr['owner'],
                        repo=pr['repo'],
                        pr_number=pr['pr_number'],
                        comment_body=comment_preview
                    )
                    st.success("Comment posted to PR")
                except Exception as e:
                    st.error(f"Failed to post comment: {e}")


