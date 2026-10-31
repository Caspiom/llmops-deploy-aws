"""Observabilidade: métricas Prometheus (latência/custo/tokens por request) +
log estruturado em JSON. É o coração do pilar — 'deploy + observabilidade'."""
from __future__ import annotations
import json
import logging
import sys
import time
from contextlib import contextmanager

from prometheus_client import Counter, Histogram

# --- Métricas (expostas em /metrics no formato Prometheus) ---
REQUESTS = Counter(
    "llmops_requests_total", "Total de requisições", ["endpoint", "status"]
)
LATENCY = Histogram(
    "llmops_request_latency_seconds",
    "Latência por requisição (s)",
    ["endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)
TOKENS = Counter("llmops_tokens_total", "Tokens processados", ["kind"])
COST = Counter(
    "llmops_estimated_cost_usd_total", "Custo estimado (USD)", ["model"]
)

# Tabela de preço ILUSTRATIVA (USD por 1k tokens). Fixture é ~grátis; os valores
# reais entram quando houver provider real. Serve p/ demonstrar o mecanismo de
# rastreio de custo por request — o diferencial do pilar.
PRICE_PER_1K = {
    "fixture-1": {"prompt": 0.00005, "completion": 0.00010},
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    p = PRICE_PER_1K.get(model, {"prompt": 0.0, "completion": 0.0})
    return (prompt_tokens / 1000) * p["prompt"] + (completion_tokens / 1000) * p[
        "completion"
    ]


# --- Log estruturado JSON (uma linha por evento; pronto p/ CloudWatch) ---
_logger = logging.getLogger("llmops")
if not _logger.handlers:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(h)
    _logger.setLevel(logging.INFO)


def log_event(**fields):
    _logger.info(json.dumps(fields, ensure_ascii=False))


@contextmanager
def observe(endpoint: str):
    """Mede latência e contabiliza status p/ um endpoint."""
    start = time.perf_counter()
    status = "ok"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        dur = time.perf_counter() - start
        LATENCY.labels(endpoint=endpoint).observe(dur)
        REQUESTS.labels(endpoint=endpoint, status=status).inc()


def record_usage(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    TOKENS.labels(kind="prompt").inc(prompt_tokens)
    TOKENS.labels(kind="completion").inc(completion_tokens)
    cost = estimate_cost(model, prompt_tokens, completion_tokens)
    COST.labels(model=model).inc(cost)
    return cost
