"""FastAPI agent for foundry-agent-demo.

Wraps a Microsoft Agent Framework ChatAgent backed by an Azure AI Foundry
project. Exposes:
  GET  /         — service info
  GET  /healthz  — liveness probe
  POST /chat     — invoke the agent ({"message": "..."})
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("foundry-agent-demo-agent")

INSTRUCTIONS = (
    "You are foundry-agent-demo, an AI agent built on Microsoft Agent Framework "
    "using the 'rag' technique. Answer the user concisely and cite "
    "sources when available."
)

_state: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    project_endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
    model_name = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")
    if not project_endpoint:
        log.warning("FOUNDRY_PROJECT_ENDPOINT not set — agent will return errors on /chat.")
        yield
        return

    # Imported lazily so the container still starts if these packages
    # are missing at build time during early iteration.
    from azure.identity.aio import DefaultAzureCredential
    from agent_framework import ChatAgent
    from agent_framework.foundry import FoundryChatClient

    credential = DefaultAzureCredential()
    client = FoundryChatClient(
        project_endpoint=project_endpoint,
        model_deployment_name=model_name,
        credential=credential,
    )
    _state["agent"] = ChatAgent(chat_client=client, instructions=INSTRUCTIONS)
    _state["credential"] = credential
    log.info("Agent initialized — project=%s model=%s", project_endpoint, model_name)
    try:
        yield
    finally:
        await credential.close()


app = FastAPI(title="foundry-agent-demo", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


@app.get("/")
def root():
    return {
        "solution": "foundry-agent-demo",
        "technique": "rag",
        "framework": "microsoft-agent-framework",
        "backend": "azure-ai-foundry",
        "endpoints": ["GET /healthz", "POST /chat"],
    }


@app.get("/healthz")
def healthz():
    return {"status": "healthy", "agent_ready": "agent" in _state}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    agent = _state.get("agent")
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized — check FOUNDRY_PROJECT_ENDPOINT.")
    try:
        result = await agent.run(req.message)
    except Exception as exc:  # noqa: BLE001
        log.exception("agent.run failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ChatResponse(response=str(result))
