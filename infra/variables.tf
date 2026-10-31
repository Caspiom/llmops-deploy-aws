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
