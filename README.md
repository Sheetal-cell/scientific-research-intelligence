# Scientific Research Intelligence

An AI-assisted scientific research workspace that turns a research question into a structured investigation: literature discovery, relevance assessment, PDF extraction, evidence extraction, cross-paper synthesis, report generation, citation checks, and PDF export.

## Project structure

```text
backend/       FastAPI API and multi-agent research pipeline
frontend/      React + TypeScript + Vite research workspace
render.yaml    Render backend deployment blueprint
```

## Features

- Research planning with Gemini structured output
- Literature discovery through OpenAlex and arXiv
- Deduplication and LLM-assisted relevance assessment
- OpenAlex retry/backoff for rate limits and transient failures
- PDF collection and text extraction
- Chunk-based scientific evidence extraction
- Cross-paper synthesis and report generation
- Citation and report-quality evaluation
- Downloadable PDF report
- Responsive React dashboard with workflow status, selected papers, report view, and quality indicators

## Run locally

### 1. Backend

Use Python 3.11 or newer.

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Add your Gemini API key to `backend/.env`. Do not commit this file.

Start the API from the `backend` directory:

```powershell
uvicorn app.main:app --reload
```

API: http://localhost:8000  
Interactive API docs: http://localhost:8000/docs  
Health check: http://localhost:8000/health

### 2. Frontend

Open a second PowerShell window:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open http://localhost:5173. The default API URL is http://localhost:8000.

## Environment variables

Backend (`backend/.env`):

| Variable | Required | Description |
| --- | --- | --- |
| `GEMINI_API_KEY` | Yes, for AI endpoints | Gemini API key; configure as a secret in hosting |
| `GEMINI_MODEL` | No | Defaults to `gemini-3.5-flash-lite` |
| `GEMINI_FALLBACK_MODEL` | No | Fallback model used on Gemini 503; defaults to `gemini-3.1-flash-lite` |
| `OPENALEX_API_KEY` | No | Contact email for OpenAlex polite identification |
| `FRONTEND_ORIGINS` | No | Comma-separated allowed frontend origins |

Frontend (`frontend/.env`):

| Variable | Description |
| --- | --- |
| `VITE_API_URL` | Backend base URL; defaults to `http://localhost:8000` |

Never put the Gemini key in a `VITE_*` variable or frontend source.

## Free-tier deployment outline

1. Deploy the backend on Render using the included `render.yaml`. Set `GEMINI_API_KEY` as a secret environment variable in the Render dashboard. Free web services may sleep when idle and take time to wake.
2. Deploy `frontend/` on Vercel with framework preset Vite. Set `VITE_API_URL` to the deployed Render API URL.
3. Update `FRONTEND_ORIGINS` on Render with the exact Vercel production origin. The API also permits Vercel preview subdomains.
4. Trigger a fresh deployment after environment variables are saved.

Free provider limits and model/API quotas can change. A successful deployment does not guarantee unlimited Gemini or OpenAlex usage.

## Reliability notes

- The API health endpoint does not require a Gemini key, so hosting health checks can succeed before secrets are configured.
- Gemini clients are initialized lazily when an AI task is requested. Missing-key errors are returned by the relevant API operation rather than preventing FastAPI startup.
- OpenAlex requests use bounded retries and respect a numeric `Retry-After` header where supplied. If a provider remains unavailable, discovery may still return fewer results; check server logs.
- PDF availability and extraction quality depend on publisher access and the source PDF. The pipeline should report partial results rather than treating every paper as fully extracted.

## Important

This is a research assistance tool, not a source of clinical, legal, or other professional advice. Verify primary sources and every citation before relying on generated summaries. Do not treat model-generated statements as established findings without checking the cited paper.
