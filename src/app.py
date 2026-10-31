"""Serviço FastAPI — hello-world do pilar LLMOps.
Endpoints:
  GET  /health    -> liveness
  POST /generate  -> chama o provider de LLM, mede latência/custo, loga
  GET  /metrics   -> métricas Prometheus (observabilidade)
"""
from __future__ import annotations
import time

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from .observability import log_event, observe, record_usage
from .providers import get_provider

app = FastAPI(title="llmops-deploy-aws", version="0.1.0")
_provider = get_provider()


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Prompt de entrada")


class GenerateResponse(BaseModel):
    text: str
    model: str
    latency_ms: float
    usage: dict
    estimated_cost_usd: float


@app.get("/health")
def health():
    return {"status": "ok", "provider": _provider.__class__.__name__}


@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    with observe("generate"):
        start = time.perf_counter()
        gen = _provider.generate(req.prompt)
        latency_ms = (time.perf_counter() - start) * 1000
        cost = record_usage(gen.model, gen.prompt_tokens, gen.completion_tokens)
        log_event(
            event="generate",
            model=gen.model,
            prompt_tokens=gen.prompt_tokens,
            completion_tokens=gen.completion_tokens,
            latency_ms=round(latency_ms, 2),
            estimated_cost_usd=round(cost, 8),
        )
        return GenerateResponse(
            text=gen.text,
            model=gen.model,
            latency_ms=round(latency_ms, 2),
            usage={
                "prompt_tokens": gen.prompt_tokens,
                "completion_tokens": gen.completion_tokens,
            },
            estimated_cost_usd=round(cost, 8),
        )


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
