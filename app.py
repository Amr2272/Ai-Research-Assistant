import streamlit as st
import requests
import time

st.set_page_config(page_title="AI Research Assistant", layout="wide")

st.title("🧠 AI Research Assistant")
st.markdown("Paste the Ngrok URL from Kaggle below.")

NGROK_URL = st.text_input("🔗 Ngrok URL", placeholder="https://<id>.ngrok-free.app")

if NGROK_URL:
    st.markdown(f"Connected to: `{NGROK_URL}`")

mode = st.radio("Input type", ["Text (research topic)", "PDF file"], horizontal=True)

topic = None
pdf_file = None

if mode == "Text (research topic)":
    topic = st.text_area("✍ Enter your research topic", height=100)
else:
    pdf_file = st.file_uploader("📄 Upload a PDF", type=["pdf"])

if st.button("🔍 Test Connection"):
    if not NGROK_URL:
        st.warning("Enter the Ngrok URL.")
    else:
        try:
            r = requests.get(f"{NGROK_URL}/health", headers={"ngrok-skip-browser-warning": "true"}, timeout=10)
            if r.status_code == 200: st.success("✅ Server is running")
            else: st.error(f"❌ Server returned {r.status_code}")
        except Exception as e: st.error(f"❌ Connection error: {e}")

st.divider()


def poll_job(ngrok_url, job_id, headers, poll_interval=3, max_wait=900):
    """Poll /status/{job_id} until it's done or errors, updating a live status message.
    Short-lived requests only, so no idle connection ever sits open for minutes."""
    status_placeholder = st.empty()
    elapsed = 0
    while elapsed < max_wait:
        try:
            resp = requests.get(f"{ngrok_url}/status/{job_id}", headers=headers, timeout=15)
        except requests.exceptions.RequestException as e:
            status_placeholder.warning(f"⚠ Poll attempt failed, retrying... ({e})")
            time.sleep(poll_interval)
            elapsed += poll_interval
            continue

        try:
            data = resp.json()
        except ValueError:
            status_placeholder.warning(f"⚠ Non-JSON response while polling (status {resp.status_code}), retrying...")
            time.sleep(poll_interval)
            elapsed += poll_interval
            continue

        status = data.get("status")

        if status == "pending":
            status_placeholder.info(f"⏳ Still processing on Kaggle... ({elapsed}s elapsed)")
            time.sleep(poll_interval)
            elapsed += poll_interval
            continue
        elif status == "error":
            status_placeholder.empty()
            return {"ok": False, "data": data}
        elif status == "done":
            status_placeholder.empty()
            return {"ok": True, "data": data}
        else:
            status_placeholder.empty()
            return {"ok": False, "data": {"error": f"Unexpected status payload: {data}"}}

    status_placeholder.empty()
    return {"ok": False, "data": {"error": f"Timed out after {max_wait}s waiting for job {job_id}."}}


if st.button("🚀 Run Research", type="primary"):
    if not NGROK_URL:
        st.warning("Enter the Ngrok URL.")
    elif mode == "Text (research topic)" and not topic:
        st.warning("Enter a topic.")
    elif mode == "PDF file" and not pdf_file:
        st.warning("Upload a PDF.")
    else:
        headers = {"ngrok-skip-browser-warning": "true"}
        job_id = None

        # Step 1: submit the job. This request is short-lived (server returns
        # a job_id immediately instead of blocking until the report is ready),
        # so it won't hit ngrok/proxy idle timeouts.
        try:
            with st.spinner("📤 Submitting job..."):
                if mode == "Text (research topic)":
                    response = requests.post(f"{NGROK_URL}/research/text", data={"topic": topic}, headers=headers, timeout=30)
                else:
                    files = {"file": (pdf_file.name, pdf_file.getvalue(), "application/pdf")}
                    response = requests.post(f"{NGROK_URL}/research/pdf", files=files, headers=headers, timeout=60)

            try:
                submit_data = response.json()
            except ValueError:
                st.error(f"❌ Server returned a non-JSON response while submitting (status {response.status_code}).")
                with st.expander("View raw response"):
                    st.code(response.text[:2000] or "(empty response body)")
                submit_data = None

            if submit_data is not None:
                if response.status_code != 200:
                    st.error(f"❌ Server Error: {submit_data.get('error', 'Unknown error')}")
                else:
                    job_id = submit_data.get("job_id")
                    if not job_id:
                        st.error("❌ Server did not return a job_id.")

        except requests.exceptions.Timeout:
            st.error("❌ Job submission timed out. Is the Kaggle notebook still running?")
        except requests.exceptions.ConnectionError as e:
            st.error(f"❌ Connection error: could not reach the Ngrok URL. Is the Kaggle notebook still running? ({e})")
        except Exception as e:
            st.error(f"❌ Unexpected error while submitting: {e}")

        # Step 2: poll for completion. Each poll request is short (a few
        # seconds), so nothing stays connected long enough to be killed.
        if job_id:
            with st.spinner("⏳ Processing on Kaggle (this can take 2-5 mins)..."):
                outcome = poll_job(NGROK_URL, job_id, headers)

            if not outcome["ok"]:
                data = outcome["data"]
                st.error(f"❌ Server Error: {data.get('error', 'Unknown error')}")
                if "trace" in data:
                    with st.expander("View Error Trace"):
                        st.code(data["trace"])
            else:
                data = outcome["data"]
                st.success(f"✅ Done: {data.get('topic','')}")
                st.subheader("📝 Report")
                st.markdown(data["report_markdown"])

                # Fetch the PDF separately via a streaming download
                # endpoint instead of a huge base64 JSON blob.
                report_id = data.get("report_id")
                if report_id:
                    try:
                        pdf_resp = requests.get(
                            f"{NGROK_URL}/download/{report_id}",
                            headers=headers,
                            timeout=120,
                        )
                        if pdf_resp.status_code == 200:
                            st.download_button(
                                "⬇ Download PDF Report",
                                data=pdf_resp.content,
                                file_name=data.get("pdf_filename", "research_report.pdf"),
                                mime="application/pdf",
                            )
                        else:
                            st.error(f"❌ Could not fetch PDF (status {pdf_resp.status_code}).")
                    except Exception as e:
                        st.error(f"❌ Error downloading PDF: {e}")
                else:
                    st.warning("⚠ No report_id returned by server; PDF unavailable.")