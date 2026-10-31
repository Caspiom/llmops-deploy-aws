# PROGRESSO — llmops-deploy-aws

Último ponto onde parei (atualize ao fim de cada sessão de 1h):

- **Data:** 2026-10-28 (sessão feita pelo Hermes a pedido do Lucas — ver `NOTAS-SESSAO-2026-10-28.md`)
- **Onde parei:** esqueleto + hello-world RODANDO. Serviço FastAPI (`/health`, `/generate`, `/metrics`) com provider `fixture` offline, observabilidade (latência/custo/tokens por request via Prometheus) e log JSON. 4 testes passando. Benchmark: p50 17,3ms / p95 18,0ms. Docker + docker-compose prontos. IaC Terraform (ECS Fargate) em ESQUELETO, não aplicado (sem gasto AWS).
- **Próximo passo:** (1) provider real barato com teto de custo + medir latência/custo reais; (2) completar a task definition/ALB no Terraform e fazer um deploy de demo com `destroy` depois; (3) OpenTelemetry → CloudWatch.
