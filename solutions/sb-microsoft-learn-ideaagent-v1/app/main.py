"""Minimal FastAPI app generated for SB-Microsoft-Learn-Ideaagent-v1."""
from fastapi import FastAPI

app = FastAPI(title="SB-Microsoft-Learn-Ideaagent-v1")


@app.get("/")
def root():
    return {"solution": "SB-Microsoft-Learn-Ideaagent-v1", "technique": "rag", "status": "ok"}


@app.get("/healthz")
def healthz():
    return {"status": "healthy"}
