# PROGRESSO — llmops-deploy-aws

Último ponto onde parei (atualize ao fim de cada sessão de 1h):

- **Data:** 2026-11-06 (bloco de SEXTA, feito pelo Hermes a pedido do Lucas)
- **Onde parei:** (1) provider `anthropic` pronto com **teto de custo duro** (reserva o pior caso sob lock antes de cada chamada, 429 ao estourar, não sobe sem teto, 502 sem vazar detalhe) + métricas de orçamento; 27 testes contra servidor HTTP falso (passam sem internet), 21 mutantes (20 pegos + 1 equivalente). (2) Terraform COMPLETO (task definition, ALB, SGs, IAM, SSM opcional): `fmt`/`validate` ok, `plan` = 12 recursos (13 com provider pago), travas de variável testadas (CIDR aberto, provider sem chave). Container Docker buildado e testado de verdade (/health, /generate, recusa subir sem teto). Modelo de custo com Pricing API: ~US$ 0,058/h.
- **O que NÃO foi feito:** nenhuma chamada paga ao LLM (sem latência/custo reais), **nenhum `apply`** (nada na AWS), OpenTelemetry→CloudWatch não começou.
- **Próximo passo:** (1) ok do Lucas para: rodada real de ~5 chamadas (pior caso ~US$ 0,0007) e/ou `apply` de demo de ~2h (~US$ 0,12) seguido de `destroy`; (2) DECIDIR a conta AWS: o CLI aponta para a conta da GaspariTec (lucas@gasparitecnologia.com.br), não uma pessoal; (3) OpenTelemetry → CloudWatch.
