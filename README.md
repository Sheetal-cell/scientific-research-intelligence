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
- LLM-assisted relevance assessment
- PDF collection and text extraction
- Chunk-based scientific evidence extraction
- Cross-paper synthesis and report generation
- Deterministic citation checks and report-quality evaluation
- Gemini primary + Gemini secondary + optional Groq emergency model fallback
- Responsive React dashboard and downloadable PDF report

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

Add your Gemini key and (recommended) Groq key to `backend/.env`. Never commit this file.

Start the API from the backend directory:

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
| `GEMINI_API_KEY` | Yes | Primary Google Gemini API key |
| `GEMINI_MODEL` | No | Defaults to `gemini-3.5-flash-lite` |
| `GEMINI_FALLBACK_MODEL` | No | Secondary Gemini model; defaults to `gemini-3.1-flash-lite` |
| `GROQ_API_KEY` | Recommended | Independent fallback when both Gemini models fail; free-tier limits apply |
| `GROQ_MODEL` | No | Defaults to `openai/gpt-oss-20b` |
| `OPENALEX_API_KEY` | No | OpenAlex API key for higher API limits |
| `FRONTEND_ORIGINS` | No | Comma-separated allowed frontend origins |

Frontend (`frontend/.env`):

| Variable | Description |
| --- | --- |
| `VITE_API_URL` | Backend base URL; defaults to `http://localhost:8000` |

Never put API keys in frontend variables or frontend source code.

## Free-tier deployment outline

1. Deploy the backend on Render using `render.yaml`.
2. Set `GEMINI_API_KEY` and `GROQ_API_KEY` as secret environment variables in Render. Do not upgrade Groq to a paid tier unless you deliberately choose to.
3. Deploy `frontend/` on Vercel with framework preset Vite and set `VITE_API_URL` to the Render API URL.
4. Set `FRONTEND_ORIGINS` on Render to your Vercel production origin and redeploy.

Provider free-tier limits and model availability can change. A successful deployment does not guarantee unlimited API usage.

## Reliability notes

- Gemini is attempted first, followed by the configured secondary Gemini model.
- If both Gemini models fail, the application uses Groq when `GROQ_API_KEY` is configured. Groq output is parsed and validated by the same Pydantic schemas used by the agents.
- Groq structured output is best-effort; schema validation remains mandatory in the application.
- OpenAlex requests use bounded retries and respect a numeric `Retry-After` header where supplied.
- PDF availability depends on publisher access and source licensing. Paywalled sources may reject downloads; the app must report those failures rather than imply the paper was analysed.

## Important

This is a research assistance tool, not a source of clinical, legal, or other professional advice. Verify primary sources and every citation before relying on generated summaries. Do not treat model-generated statements as established findings without checking the cited paper.
