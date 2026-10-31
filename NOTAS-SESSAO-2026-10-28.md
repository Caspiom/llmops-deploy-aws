# Notas da sessão — 2026-10-28 (feita pelo Hermes)

Oi Lucas! Você não conseguiu fazer o bloco de hoje (`llmops-deploy-aws`) e pediu
pra eu começar. Aqui está, resumidinho, **o que foi feito** pra você dar uma
olhadinha. Depois você me conta o que achou. 🙂

## O que eu entreguei (hello-world do pilar, RODANDO)
Um serviço de LLMOps mínimo, mas de verdade — o pilar é "deploy + observabilidade",
então o foco foi **medir custo e latência por request**, não só responder.

- **Serviço FastAPI** (`src/app.py`): `GET /health`, `POST /generate`, `GET /metrics`.
- **Provider de LLM plugável** (`src/providers.py`): hoje usa o `fixture` —
  offline, determinístico, **sem chave e sem custo**. Provider real entra depois,
  atrás da env `LLM_PROVIDER`, sem quebrar o fluxo grátis.
- **Observabilidade** (`src/observability.py`): métricas Prometheus (contador de
  requests, histograma de latência, tokens, **custo estimado por request**) +
  log estruturado em JSON (pronto pra CloudWatch).
- **Docker + docker-compose** (compose tem um profile `obs` que sobe Prometheus
  pra ver os gráficos localmente).
- **Terraform** em `infra/` (ECR + ECS Fargate + log group): **ESQUELETO, não
  apliquei nada na AWS** — aplicar custa dinheiro, então deixei a planta pronta
  e documentei o custo. (Respeitei tua regra: validar de graça primeiro.)
- **4 testes** (`tests/test_app.py`) passando.

## Provas de que roda (rodei de verdade aqui)
- `pytest` → **4 passed**.
- `GET /health` → `{"status":"ok","provider":"FixtureProvider"}`.
- `POST /generate {"prompt":"Ola, LLMOps!"}` → texto + `latency_ms:15.2` + usage + custo.
- `bench.py` (50 reqs) → **p50 17,3 ms · p95 18,0 ms · custo total ~US$6,5e-05**.
- `/metrics` expõe `llmops_requests_total`, `llmops_tokens_total`, `llmops_estimated_cost_usd_total`.

## Decisões que tomei (e por quê)
1. **Provider `fixture` em vez de LLM real** → zero custo, zero chave, roda offline.
   O pilar não precisa de um modelo real pra provar deploy/observabilidade.
2. **NÃO provisionei a AWS** → `terraform apply` gasta. Deixei a IaC como esqueleto
   e uma nota de custo (Fargate ~US$9–12/mês 24/7, ou Lambda ~US$0 ocioso).
   Quando for gravar a demo, a gente sobe e dá `destroy` depois (centavos).
3. **Prometheus em vez de OpenTelemetry (por ora)** → é o "hello-world" de
   observabilidade mais fácil de mostrar número. O README já lista OTel/CloudWatch
   como próximo passo. (Atualizei a linha de stack do README pra refletir o que
   realmente tem hoje — não quis prometer OTel sem ter implementado.)

## O que você deve conferir
- Abra o `README.md` (tem a tabela de números e o "como rodar" em < 15 min).
- Se quiser ver rodando: `python3 -m venv .venv && . .venv/bin/activate &&
  pip install -r requirements.txt && pytest -q && uvicorn src.app:app --reload`.

## Próximo passo (pra tua próxima sessão)
1. Plugar um **provider real barato com teto de custo** e medir latência/custo reais.
2. Completar a **task definition + ALB** no Terraform e fazer **um** deploy de demo
   (com `destroy` depois).
3. **OpenTelemetry → CloudWatch** pra fechar a história de observabilidade na AWS.

> Commit desta sessão feito como **Gappy <lucasamsg6@gmail.com>** e pushado pro
> `github.com/Caspiom/llmops-deploy-aws`. Me fala o que achou! 🚀
