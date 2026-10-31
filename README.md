# llmops-deploy-aws

> **Pilar do portfólio — Sexta** · parte de uma série de 7 projetos de Engenharia de Software de IA (1h/dia).

## O problema
Colocar um serviço de LLM de pé com **Docker**, **logging estruturado** e **observabilidade de custo/latência por request** — e deixar o caminho de **deploy na AWS** pronto (IaC declarativa), com benchmark medido.

## Por que está no portfólio
Deploy + observabilidade (custo/latência) na AWS. O diferencial é **execução com número medido**, não só demo: cada request expõe latência, tokens e custo estimado em `/metrics` (Prometheus).

## Stack
FastAPI · Prometheus (métricas) · logging JSON · Docker/Compose · Terraform (AWS ECS Fargate) · provider de LLM plugável (`fixture` offline agora; real atrás de env)

## Hello-world (rodando, grátis)
Provider `fixture` offline e determinístico — o esqueleto roda **sem chave de API e sem custo**. Provider real entra numa próxima sessão, com teto de custo.

### Números medidos (50 requests, provider fixture, local)
| Métrica | Valor |
|---|---|
| Latência p50 | **17,3 ms** |
| Latência p95 | **18,0 ms** |
| Latência máx | 18,7 ms |
| Custo estimado (50 reqs) | ~US$6,5e-05 (tabela ilustrativa) |
| Testes | **4 passando** (`pytest`) |

> Custo é rastreado por request via `/metrics` — o mecanismo é o entregável; os preços reais entram com o provider real.

## Como rodar (< 15 min)
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# testes
pytest -q

# subir o serviço
uvicorn src.app:app --reload
# em outro terminal:
curl localhost:8000/health
curl -X POST localhost:8000/generate -H 'Content-Type: application/json' -d '{"prompt":"Ola, LLMOps!"}'
curl localhost:8000/metrics          # métricas Prometheus
python bench.py 50                    # benchmark de latência/custo
```
Docker: `docker compose up app` (API) · `docker compose --profile obs up` (API + Prometheus em :9090).

## Estrutura
- `src/` — serviço FastAPI (`app.py`), provider de LLM (`providers.py`), observabilidade (`observability.py`)
- `tests/` — testes (pytest)
- `bench.py` — mini-benchmark de latência/custo
- `infra/` — Terraform do deploy AWS (**esqueleto, NÃO aplicado** — ver `infra/README.md`)
- `dashboards/` — `prometheus.yml` (scrape local)

## Status
- [x] Esqueleto / setup roda em < 15 min
- [x] Núcleo funcional (happy path: /health, /generate, /metrics)
- [x] Observabilidade medida (latência + custo + tokens por request)
- [x] README com números (latência, custo)
- [ ] Deploy / demo reproduzível na AWS (IaC em esqueleto; aplicar depois com teto de custo)
- [ ] Provider real (com cost cap) + OpenTelemetry/CloudWatch

---
Autor: Gappy · Série montada com apoio do Hermes
