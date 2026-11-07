# Deploy do serviço FastAPI em ECS Fargate atrás de um ALB.
# Desenho de CUSTO MÍNIMO para demo: VPC default, sem NAT Gateway (a task usa IP público
# só para puxar a imagem/falar com a API), 1 task x86 0.25 vCPU / 0.5 GB.
# NÃO APLICAR sem estimativa de custo + ok (ver infra/README.md). Sempre `terraform destroy` depois.

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

  default_tags {
    tags = {
      Project   = var.service_name
      ManagedBy = "terraform"
      Purpose   = "portfolio-demo-destroy-after"
    }
  }
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

locals {
  # O ALB exige >= 2 AZs e cobra 1 IPv4 publico (US$0,005/h) por subnet: usar so 2, nao as 6 da VPC default.
  subnet_ids = slice(sort(data.aws_subnets.default.ids), 0, 2)
}

# --- Registry da imagem ---------------------------------------------------------------
resource "aws_ecr_repository" "app" {
  name                 = var.service_name
  force_delete         = true # destroy limpo mesmo com imagem dentro
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# --- Logs estruturados JSON -----------------------------------------------------------
resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.service_name}"
  retention_in_days = var.log_retention_days
}

# --- Rede: ALB só aceita o CIDR liberado; a task só aceita o ALB ----------------------
resource "aws_security_group" "alb" {
  name_prefix = "${var.service_name}-alb-"
  description = "ALB: entrada so de allowed_cidr na porta 80"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTP do CIDR liberado"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = [var.allowed_cidr]
  }

  egress {
    description = "ALB para as tasks"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.default.cidr_block]
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "task" {
  name_prefix = "${var.service_name}-task-"
  description = "Task: entrada so do ALB na 8000"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "Do ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "ECR, CloudWatch e API do provider (HTTPS)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

# --- ALB ------------------------------------------------------------------------------
resource "aws_lb" "app" {
  name               = var.service_name
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = local.subnet_ids
}

resource "aws_lb_target_group" "app" {
  name_prefix = "llm-"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = data.aws_vpc.default.id

  deregistration_delay = 5 # demo: derruba rápido

  health_check {
    path                = "/health"
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# --- IAM: a task puxa imagem, escreve log e (opcional) lê a chave no SSM --------------
data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name_prefix        = "${var.service_name}-exec-"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "read_key" {
  count = var.anthropic_key_ssm_arn == "" ? 0 : 1
  name  = "read-anthropic-key"
  role  = aws_iam_role.execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ssm:GetParameters"]
      Resource = [var.anthropic_key_ssm_arn]
    }]
  })
}

# --- Task + Service -------------------------------------------------------------------
resource "aws_ecs_cluster" "this" {
  name = var.service_name
}

resource "aws_ecs_task_definition" "app" {
  family                   = var.service_name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.execution.arn

  container_definitions = jsonencode([{
    name      = "app"
    image     = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
    essential = true

    portMappings = [{ containerPort = 8000, protocol = "tcp" }]

    environment = [
      { name = "LLM_PROVIDER", value = var.llm_provider },
      { name = "LLM_MAX_COST_USD", value = tostring(var.llm_max_cost_usd) },
    ]

    secrets = var.anthropic_key_ssm_arn == "" ? [] : [
      { name = "ANTHROPIC_API_KEY", valueFrom = var.anthropic_key_ssm_arn }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.region
        awslogs-stream-prefix = "app"
      }
    }
  }])
}

resource "aws_ecs_service" "app" {
  name            = var.service_name
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = local.subnet_ids
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = true # sem NAT Gateway (~US$32/mes): so sai para ECR/HTTPS
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "app"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.http]
}
