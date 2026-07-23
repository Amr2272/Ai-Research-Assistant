# 🧠 AI Research Assistant

A multi-agent AI research assistant that takes a text topic or a PDF and produces a full academic-style research report (with a downloadable PDF). The heavy LLM work runs for free on a Kaggle GPU notebook; a lightweight Streamlit app is the client UI, connected to Kaggle over an Ngrok tunnel.

## Architecture

```
┌─────────────────────┐        Ngrok tunnel        ┌──────────────────────────────┐
│   Streamlit App      │ ───────────────────────── │   Kaggle Notebook (GPU)       │
│   (app.py)            │   HTTPS + submit/poll     │   FastAPI + Multi-Agent       │
│   - Text or PDF input │                            │   Pipeline (Qwen2.5-7B)       │
│   - Job polling UI    │                            │   /research/text, /research/pdf│
│   - Report + PDF view │                            │   /status/{job_id}, /download │
└─────────────────────┘                             └──────────────────────────────┘
```

The backend uses a **submit-and-poll** design instead of one long blocking request: the client posts the job, gets a `job_id` back immediately, then polls `/status/{job_id}` every few seconds. This avoids Ngrok/proxy timeouts on long-running LLM jobs (2–5 minutes).

### Multi-agent pipeline (runs on Kaggle)

| Agent | Responsibility |
|---|---|
| **PlannerAgent** | Parses the text/PDF input and builds a structured research plan (topic, subtopics, keywords, depth) |
| **RetrievalAgent** | Runs web searches (DuckDuckGo) based on the plan and collects source documents |
| **AnalysisAgent** | Synthesizes retrieved documents into themes, key findings, comparisons, and conflicts (structured JSON) |
| **ReportAgent** | Turns the analysis into a formatted Markdown academic report |
| **ExportAgent** | Renders the final report to a downloadable PDF (ReportLab) |

`AIResearchAssistant` orchestrates all five agents in sequence, backed by a single shared `Qwen/Qwen2.5-7B-Instruct` model loaded in 4-bit (via `transformers` + `bitsandbytes`) and wrapped as a LangChain `HuggingFacePipeline`.

## Repository layout

```
.
├── app.py                              # Streamlit client
├── ai-research-assistant-project.ipynb # Kaggle notebook: agents + FastAPI + Ngrok server
├── requirements.txt                    # Deps for the Streamlit client and Kaggle notebook
```

## Setup

### 1. Backend — Kaggle notebook

1. Open `ai-research-assistant-project.ipynb` in Kaggle with a **GPU** runtime (T4/P100).
2. Add your Ngrok authtoken as a Kaggle secret (or set it directly in the notebook) and run all cells.
3. The last cell starts the FastAPI server and opens an Ngrok tunnel, printing a public URL like:
   ```
   https://<random-id>.ngrok-free.app
   ```
4. Keep the notebook running — the tunnel and model stay alive only while the Kaggle session is active.

### 2. Client — Streamlit app

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then in the app:
1. Paste the Ngrok URL printed by the Kaggle notebook.
2. Click **Test Connection** to confirm the backend is reachable (`/health`).
3. Choose **Text** (enter a research topic) or **PDF** (upload a file).
4. Click **Run Research** — the app submits the job, polls for progress, then displays the Markdown report and a PDF download button.

## API endpoints (backend)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/research/text` | Submit a text topic (`topic` form field) → returns `{job_id}` |
| `POST` | `/research/pdf` | Submit a PDF file (`file` upload) → returns `{job_id}` |
| `GET` | `/status/{job_id}` | Poll job status: `pending` / `done` / `error` |
| `GET` | `/download/{report_id}` | Download the generated PDF report |

## Notes / limitations

- The backend only stays online as long as the Kaggle notebook session and Ngrok tunnel are running.
- Free Ngrok URLs change on every restart — re-paste the URL into the Streamlit app each session.
- Report quality depends on DuckDuckGo search results; if too few sources are found, the report will explicitly state missing topics rather than inventing information.
