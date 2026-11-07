# Infra AWS (Terraform) - COMPLETO, VALIDADO, NAO APLICADO

> Nada foi provisionado na AWS. `terraform validate` e `terraform plan` passam (12 recursos; 13 com o provider pago), mas **nunca houve `apply`**.
> Aplicar custa dinheiro: so com teto aprovado e `destroy` logo depois.

## O que sobe
ECS Fargate (1 task x86, 0,25 vCPU / 0,5 GB) atras de um ALB, imagem no ECR, logs JSON no CloudWatch (retencao 3 dias).
Custo minimo de proposito: VPC default, **sem NAT Gateway** (~US$ 32/mes), ALB e task em so **2 subnets** (a VPC default de us-east-1 tem 6; o ALB poe 1 IPv4 publico de US$ 0,005/h em cada).

Seguranca: o endpoint nao tem autenticacao, entao `allowed_cidr` **nao tem default** e rejeita `0.0.0.0/0`. A task so aceita o ALB. A chave da Anthropic vem de um SSM Parameter SecureString criado **fora** do Terraform (nao vai pro tfstate) e so e lida se `llm_provider=anthropic`.

## Custo (modelo reproduzivel: `python docs/modelo-custo.py`)
Precos da Pricing API (us-east-1, 2026-11-06): ~**US$ 0,058/hora** (~R$ 0,32) = Fargate 0,0123 + ALB 0,0225 + LCU 0,008 + 3 IPv4 0,015. Uma demo de 2h ~US$ 0,12. **24/7 seria ~US$ 42/mes: nao deixar rodando.**
Isso e *estimativa*; ainda nao ha fatura real. O custo do LLM e separado e tem teto proprio (`llm_max_cost_usd`).

## Fluxo (ordem importa: a imagem precisa existir antes do service)
```bash
cd infra
terraform init
terraform apply -target=aws_ecr_repository.app -var allowed_cidr=SEU_IP/32    # 1) so o ECR
# 2) build + push da imagem para a URL do output ecr_repository_url (aws ecr get-login-password | docker login ...)
terraform apply -var allowed_cidr=SEU_IP/32                                     # 3) o resto
curl $(terraform output -raw alb_url)/health
terraform destroy -var allowed_cidr=SEU_IP/32                                   # SEMPRE
```
Com o provider pago: `-var llm_provider=anthropic -var llm_max_cost_usd=0.05 -var anthropic_key_ssm_arn=arn:aws:ssm:...`.

## Limites (leia antes de aplicar)
- **O teto do LLM e por processo.** Se a task reiniciar, o contador zera: o pior caso real e `teto x numero de reinicios`. Por isso `desired_count=1`, demo curta e um limite de gasto tambem no console da Anthropic.
- Conta: o `aws` CLI desta maquina aponta para a conta da **GaspariTec**, nao uma pessoal. Decidir conscientemente onde aplicar.
- OpenTelemetry -> CloudWatch **nao foi feito** (hoje: logs JSON no CloudWatch + `/metrics` Prometheus sem coletor na AWS).
