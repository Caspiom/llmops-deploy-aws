variable "region" {
  description = "Região AWS do deploy"
  type        = string
  default     = "us-east-1"
}

variable "service_name" {
  description = "Nome do serviço / repo ECR / cluster"
  type        = string
  default     = "llmops-deploy-aws"
}

variable "cpu" {
  description = "CPU da task Fargate (unidades: 256 = 0.25 vCPU)"
  type        = number
  default     = 256
}

variable "memory" {
  description = "Memória da task Fargate (MB)"
  type        = number
  default     = 512
}

variable "desired_count" {
  description = "Número de tasks. 0 = derruba o compute sem destruir o resto (ALB continua cobrando)."
  type        = number
  default     = 1
}

variable "image_tag" {
  description = "Tag da imagem no ECR (a imagem precisa ser enviada ANTES do apply completo)"
  type        = string
  default     = "latest"
}

variable "allowed_cidr" {
  description = "CIDR que pode acessar o ALB (ex.: SEU_IP/32). Sem default de propósito: o endpoint não tem autenticação."
  type        = string

  validation {
    condition     = can(cidrhost(var.allowed_cidr, 0)) && var.allowed_cidr != "0.0.0.0/0"
    error_message = "allowed_cidr deve ser um CIDR válido e NÃO pode ser 0.0.0.0/0 (endpoint sem autenticação)."
  }
}

variable "llm_provider" {
  description = "fixture (grátis, offline) ou anthropic (gasta; exige llm_max_cost_usd e anthropic_key_ssm_arn)"
  type        = string
  default     = "fixture"

  validation {
    condition     = contains(["fixture", "anthropic"], var.llm_provider)
    error_message = "llm_provider deve ser fixture ou anthropic."
  }
}

variable "llm_max_cost_usd" {
  description = "TETO DURO de gasto do provider em US$ (vale por processo; reiniciar a task zera o contador!)"
  type        = number
  default     = 0.05
}

variable "anthropic_key_ssm_arn" {
  description = "ARN de um SSM Parameter SecureString com a ANTHROPIC_API_KEY (criado FORA do Terraform, para a chave não ir ao tfstate)"
  type        = string
  default     = ""

  validation {
    condition     = var.llm_provider != "anthropic" || var.anthropic_key_ssm_arn != ""
    error_message = "llm_provider=anthropic exige anthropic_key_ssm_arn."
  }
}

variable "log_retention_days" {
  description = "Retenção do log group (demo: curto)"
  type        = number
  default     = 3
}
