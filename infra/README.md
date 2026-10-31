# Infra AWS (Terraform) — ESQUELETO, NÃO APLICADO

> ⚠️ **Nada foi provisionado na AWS.** Isto é a planta declarativa do deploy.
> Aplicar custa dinheiro — só rodar `terraform apply` após estimativa de custo
> e aprovação explícita. O hello-world roda 100% local e grátis (Docker/uvicorn).

## Alvo de deploy
Serviço `llmops-deploy-aws` (FastAPI) como container em **ECS Fargate** atrás de
um ALB, com logs no **CloudWatch** e métricas Prometheus em `/metrics`
(scrape via ADOT/AMP numa próxima iteração).

## Arquivos
- `main.tf` — ECR (imagem) + ECS Fargate service + task role + log group.
- `variables.tf` — região, nome, CPU/mem, tamanho do container.
- `outputs.tf` — URL do serviço / nome do cluster.

## Fluxo quando for a hora (com teto de custo)
```
terraform init
terraform plan            # revisar recursos + custo estimado ANTES
terraform apply           # só após aprovação
terraform destroy         # derrubar p/ não deixar custo rodando
```

## Nota de custo (estimativa, validar antes)
Fargate 0.25 vCPU / 0.5 GB rodando 24/7 ≈ US$9–12/mês + ALB (~US$16/mês) +
CloudWatch (centavos). Para portfólio/demo: subir só quando for gravar o vídeo
e `destroy` depois — custo de poucos centavos/hora. Alternativa mais barata:
Lambda + API Gateway (paga por request, ~US$0 ocioso).
