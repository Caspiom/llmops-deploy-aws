"""Mini-benchmark: dispara N requisições em /generate e reporta
p50/p95 de latência e custo estimado total. Alimenta os 'números' do README.

Uso: python bench.py [N] [URL]   (default: 50, http://127.0.0.1:8000)
"""
import json
import statistics
import sys
import time

import httpx

N = int(sys.argv[1]) if len(sys.argv) > 1 else 50
URL = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000"

lat = []
cost_total = 0.0
with httpx.Client(base_url=URL, timeout=10) as c:
    for i in range(N):
        t = time.perf_counter()
        r = c.post("/generate", json={"prompt": f"requisicao de benchmark #{i}"})
        lat.append((time.perf_counter() - t) * 1000)
        r.raise_for_status()
        cost_total += r.json()["estimated_cost_usd"]

lat.sort()
out = {
    "requests": N,
    "latency_ms": {
        "p50": round(statistics.median(lat), 2),
        "p95": round(lat[int(0.95 * len(lat)) - 1], 2),
        "max": round(lat[-1], 2),
    },
    "estimated_cost_usd_total": round(cost_total, 8),
}
print(json.dumps(out, indent=2))
