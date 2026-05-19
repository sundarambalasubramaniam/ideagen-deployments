"""FastAPI agent for foundry-agent-demo.

Wraps a Microsoft Agent Framework Agent backed by an Azure AI Foundry
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
from fastapi.responses import HTMLResponse
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
    from agent_framework import Agent
    from agent_framework.foundry import FoundryChatClient

    credential = DefaultAzureCredential()
    client = FoundryChatClient(
        project_endpoint=project_endpoint,
        model=model_name,
        credential=credential,
    )
    _state["agent"] = Agent(client=client, name="foundry-agent-demo-agent", instructions=INSTRUCTIONS)
    _state["credential"] = credential
    log.info("Agent initialized — project=%s model=%s", project_endpoint, model_name)
    try:
        yield
    finally:
        await credential.close()


app = FastAPI(title="foundry-agent-demo", lifespan=lifespan)


_CHAT_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<title>foundry-agent-demo — chat</title>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<style>
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,Segoe UI,Roboto,sans-serif;background:#0b1020;color:#e7ecf3;display:flex;flex-direction:column;height:100vh}
header{padding:12px 20px;background:#111a35;border-bottom:1px solid #1f2a4d;font-weight:600}
header small{opacity:.6;font-weight:400;margin-left:8px}
#log{flex:1;overflow-y:auto;padding:20px;max-width:860px;width:100%;margin:0 auto}
.msg{margin:10px 0;padding:12px 16px;border-radius:12px;line-height:1.5;white-space:pre-wrap}
.user{background:#1e3a8a;align-self:flex-end;margin-left:60px}
.bot{background:#1c2540;margin-right:60px}
.err{background:#5a1a1a;color:#fecaca}
form{display:flex;gap:8px;padding:14px;border-top:1px solid #1f2a4d;background:#0e1530;max-width:860px;width:100%;margin:0 auto}
input{flex:1;padding:12px 14px;border-radius:10px;border:1px solid #2a3766;background:#0b1226;color:#e7ecf3;font-size:14px}
button{padding:0 22px;border-radius:10px;border:0;background:#3b82f6;color:#fff;font-weight:600;cursor:pointer}
button:disabled{opacity:.5;cursor:wait}
</style></head><body>
<header>foundry-agent-demo<small>microsoft agent framework · azure ai foundry</small></header>
<div id="log"></div>
<form id="f"><input id="m" autocomplete="off" placeholder="Ask the agent…" autofocus/><button id="b">Send</button></form>
<script>
const log=document.getElementById('log'),f=document.getElementById('f'),m=document.getElementById('m'),b=document.getElementById('b');
function add(text,cls){const d=document.createElement('div');d.className='msg '+cls;d.textContent=text;log.appendChild(d);log.scrollTop=log.scrollHeight;return d}
add('Hi! Ask me anything.','bot');
f.addEventListener('submit',async e=>{
  e.preventDefault();const msg=m.value.trim();if(!msg)return;
  add(msg,'user');m.value='';b.disabled=true;
  const thinking=add('…','bot');
  try{
    const r=await fetch('/chat',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({message:msg})});
    const j=await r.json();thinking.remove();
    if(!r.ok){add('Error: '+(j.detail||r.statusText),'err')}else{add(j.response,'bot')}
  }catch(err){thinking.remove();add('Network error: '+err.message,'err')}
  finally{b.disabled=false;m.focus()}
});
</script></body></html>"""


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


@app.get("/", response_class=HTMLResponse)
def root():
    return _CHAT_HTML


@app.get("/info")
def info():
    return {
        "solution": "foundry-agent-demo",
        "technique": "rag",
        "framework": "microsoft-agent-framework",
        "backend": "azure-ai-foundry",
        "endpoints": ["GET /healthz", "POST /chat", "GET /info"],
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
