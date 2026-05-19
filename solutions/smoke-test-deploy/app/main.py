"""Minimal FastAPI app generated for smoke-test-deploy."""
from fastapi import FastAPI

app = FastAPI(title="smoke-test-deploy")


@app.get("/")
def root():
    return {"solution": "smoke-test-deploy", "technique": "rag", "status": "ok"}


@app.get("/healthz")
def healthz():
    return {"status": "healthy"}
