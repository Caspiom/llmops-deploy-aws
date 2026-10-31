output "ecr_repository_url" {
  description = "URL do repositório ECR para push da imagem"
  value       = aws_ecr_repository.app.repository_url
}

output "cluster_name" {
  description = "Nome do cluster ECS"
  value       = aws_ecs_cluster.this.name
}

output "log_group" {
  description = "Log group do CloudWatch"
  value       = aws_cloudwatch_log_group.app.name
}
