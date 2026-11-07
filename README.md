# llmops-deploy-aws

> **Pilar do portfólio — Sexta** · parte de uma série de 7 projetos de Engenharia de Software de IA (1h/dia).

## O problema
Colocar um serviço de LLM de pé com **Docker**, **logging estruturado** e **observabilidade de custo/latência por request** — e deixar o caminho de **deploy na AWS** pronto (IaC declarativa), com benchmark medido.

## Por que está no portfólio
Deploy + observabilidade (custo/latência) na AWS. O diferencial é **execução com número medido**, não só demo: cada request expõe latência, tokens e custo estimado em `/metrics` (Prometheus).

## Stack
FastAPI · Prometheus (métricas) · logging JSON · Docker/Compose · Terraform (AWS ECS Fargate) · provider de LLM plugável (`fixture` offline agora; real atrás de env)

## Provider
`LLM_PROVIDER=fixture` (padrão): offline e determinístico, roda **sem chave e sem custo** (testes, CI, Docker).
`LLM_PROVIDER=anthropic`: `claude-haiku-5-5` (US$ 0,10 entrada / US$ 0,50 saída por MTok, doc de 2026-11-05) com **teto de custo duro** (`LLM_MAX_COST_USD`, obrigatório: sem ele o serviço nem sobe).

- **Reserva o pior caso antes de cada chamada** (entrada em limite superior = bytes+32, mais `max_tokens` de saída) **sob lock**; depois ajusta para o custo real. Requisições concorrentes não furam o teto (teste com 20 threads).
- Estourou: o modelo **não é chamado**, `/generate` devolve 429 e a métrica `llmops_budget_rejected_total` sobe. Falha do provider: 502 sem vazar detalhe nem chave.
- Timeout/conexão cortada depois do envio é cobrança ambígua: a reserva do pior caso fica. Retry só em 429/5xx. Thinking desligado (seria cobrado como saída).
- Métricas novas: `llmops_budget_spent_usd`, `llmops_budget_limit_usd`, `llmops_budget_rejected_total`.
- **Limite honesto:** o teto vale por processo; reiniciar zera o contador (ver `infra/README.md`).


### Números medidos (50 requests, provider fixture, local)
| Métrica | Valor |
|---|---|
| Latência p50 | **17,3 ms** |
| Latência p95 | **18,0 ms** |
| Latência máx | 18,7 ms |
| Custo estimado (50 reqs) | ~US$6,5e-05 (tabela ilustrativa) |
| Testes | **27 passando** (`pytest`), também sem internet |

> Medido com o provider `fixture`. **Latência e custo REAIS do provider Anthropic ainda não foram medidos** (nenhuma chamada paga foi feita; pedem ok de gasto). Pior caso por chamada com `max_tokens=256`: ~US$ 0,00013.

### Como foi validado sem gastar
27 testes contra um servidor HTTP falso (grava cada requisição), na suíte também rodando num namespace de rede sem internet. **21 mutantes: 20 pegos + 1 equivalente** (a checagem de teto do `get_provider` é redundante com a do construtor). Na 1ª rodada 18 foram pegos; os 2 reais que sobreviveram (fronteira `>` vs `>=` e o contador de barrados) viraram teste. O servidor falso valida o contrato HTTP que li na doc, não a API real.

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
- `infra/` — Terraform completo (ECS Fargate + ALB + ECR + IAM), **validado e com `plan` ok, NUNCA aplicado** — ver `infra/README.md`
- `docs/modelo-custo.py` — custo/hora da infra a partir da Pricing API (~US$ 0,058/h)
- `dashboards/` — `prometheus.yml` (scrape local)

## Status
- [x] Esqueleto / setup roda em < 15 min
- [x] Núcleo funcional (happy path: /health, /generate, /metrics)
- [x] Observabilidade medida (latência + custo + tokens por request)
- [x] README com números (latência, custo)
- [x] Provider real com teto de custo duro, validado de graça (27 testes, 21 mutantes)
- [x] Terraform completo (task definition, ALB, SGs, IAM), `validate` + `plan` ok
- [ ] Medir latência/custo REAIS do provider (pede ok de gasto, ~US$ 0,0007 no pior caso para 5 chamadas)
- [ ] `apply` de demo + `destroy` (pede ok: ~US$ 0,12 por 2h e decisão sobre a conta AWS)
- [ ] OpenTelemetry → CloudWatch

---
Autor: Gappy · Série montada com apoio do Hermes
