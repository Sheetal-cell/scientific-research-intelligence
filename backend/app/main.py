
from fastapi import FastAPI

app = FastAPI(
    title="Scientific Research Intelligence",
    description="A multi-agent AI research platform",
    version="0.1.0"
)

@app.get("/")
def home():
    return {
        "message": "Scientific Research Intelligence API",
        "status": "running"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }