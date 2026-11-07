"""Modelo de custo do demo na AWS (ALB + 1 task Fargate). Reproduzivel: python docs/modelo-custo.py

Precos: AWS Pricing API (aws pricing get-products --region us-east-1), regiao us-east-1,
snapshot de 2026-11-06. Precos mudam: refaca a consulta antes de decidir.
  Fargate vCPU      USE1-Fargate-vCPU-Hours:perCPU  0.04048 /vCPU-h
  Fargate memoria   USE1-Fargate-GB-Hours           0.004445 /GB-h
  ALB               LoadBalancerUsage               0.0225 /h
  ALB LCU           LCUUsage                        0.008 /LCU-h
  IPv4 publico      USE1-PublicIPv4:InUseAddress    0.005 /h
Cambio: argumento opcional (padrao 5.50 BRL/USD; em 2026-11-06 o bid era 5.503).
"""
import sys

CAMBIO = float(sys.argv[1]) if len(sys.argv) > 1 else 5.50
VCPU_H, GB_H, ALB_H, LCU_H, IPV4_H = 0.04048, 0.004445, 0.0225, 0.008, 0.005

CPU, MEM_GB = 0.25, 0.5           # task: 256 / 512 do variables.tf
TASKS = 1
ALB_IPS = 2                        # 2 subnets (main.tf: local.subnet_ids)
LCU = 1                            # piso de 1 LCU/h: o demo e trafego desprezivel

linhas = {
    "Fargate (vCPU)": CPU * VCPU_H * TASKS,
    "Fargate (memoria)": MEM_GB * GB_H * TASKS,
    "ALB (hora)": ALB_H,
    "ALB (LCU, piso)": LCU * LCU_H,
    "IPv4 publico do ALB": ALB_IPS * IPV4_H,
    "IPv4 publico da task": TASKS * IPV4_H,
}
total_h = sum(linhas.values())

print(f"{'item':<24}{'US$/h':>10}")
for k, v in linhas.items():
    print(f"{k:<24}{v:>10.5f}")
print(f"{'TOTAL':<24}{total_h:>10.5f}   (cambio {CAMBIO:.2f})\n")
for nome, horas in (("1 hora de demo", 1), ("2 horas (apply + gravar + destroy)", 2), ("24/7 por 30 dias (NAO fazer)", 720)):
    print(f"{nome:<36} US$ {total_h * horas:>8.2f}   R$ {total_h * horas * CAMBIO:>8.2f}")
print("\nFora do modelo (centavos): CloudWatch Logs (3 dias de retencao), ECR (imagem ~150 MB), trafego de saida (100 GB/mes gratis).")
print("Fora do modelo (PIOR risco): custo do LLM. Tem teto proprio (LLM_MAX_COST_USD) e e separado da infra.")
