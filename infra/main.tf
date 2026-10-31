# Esqueleto de deploy — ECS Fargate. NÃO APLICAR sem estimativa de custo + ok.
# Mantido mínimo e comentado de propósito: a planta existe, o provisionamento
# fica para uma sessão futura (ver infra/README.md).

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

# Registry da imagem do container.
resource "aws_ecr_repository" "app" {
  name = var.service_name
}

# Log group (observabilidade — logs estruturados JSON do serviço).
resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.service_name}"
  retention_in_days = 14
}

# Cluster ECS Fargate.
resource "aws_ecs_cluster" "this" {
  name = var.service_name
}

# TODO (próxima sessão): task definition + service + ALB + security groups.
# Deixado explícito para não dar a falsa impressão de que já deploya.
