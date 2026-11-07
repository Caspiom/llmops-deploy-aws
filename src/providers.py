"""Providers de LLM atrás de LLM_PROVIDER.

- `fixture` (padrão): offline, grátis, determinístico. É o que roda em testes e no CI.
- `anthropic`: Messages API (só stdlib) com TETO DE CUSTO DURO para a vida do processo.
  Antes de cada chamada (e de cada retry) RESERVA o pior caso (entrada no limite superior +
  max_tokens de saída) sob lock; se `gasto + reservas + pior caso > teto`, o modelo não é
  chamado. Depois ajusta a reserva para o custo real. Sem teto configurado, nem sobe.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable


class BudgetExceeded(Exception):
    """O pior caso da chamada estouraria o teto: o modelo NÃO foi chamado."""


class ProviderError(Exception):
    """Falha do provider que não é de orçamento (auth, 4xx, rede esgotada...)."""


@dataclass
class Generation:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int


def _count_tokens(s: str) -> int:
    # Aproximação barata (~4 chars/token) usada só pelo fixture.
    return max(1, len(s) // 4)


class FixtureProvider:
    """LLM falso, determinístico e offline. Latência simulada pequena para que
    as métricas de latência tenham um número real de verdade no histograma."""

    model = "fixture-1"

    def generate(self, prompt: str) -> Generation:
        time.sleep(0.015)  # simula custo de inferência (~15ms)
        h = hashlib.sha256(prompt.encode()).hexdigest()[:8]
        text = f"[fixture] eco de {len(prompt)} chars (hash {h})"
        return Generation(text, self.model, _count_tokens(prompt), _count_tokens(text))


# US$ por milhão de tokens (entrada, saída), prompts até 100k tokens.
# Fonte: https://platform.claude.com/docs/en/about-claude/pricing (conferido em 2026-11-05).
# Fica aqui (e não só em observability) porque o TETO depende do preço: modelo fora da
# tabela exige LLM_PRICE_IN/LLM_PRICE_OUT, nunca assumimos preço.
PRICES_USD_PER_MTOK = {"claude-haiku-5-5": (0.10, 0.50)}
PRICE_TIER_LIMIT_TOKENS = 100_000
RETRYABLE_STATUS = {429, 500, 502, 503, 504, 529}
NOT_SENT = (ConnectionRefusedError, socket.gaierror)  # nunca chegou ao servidor: não cobra
PROMPT_OVERHEAD_TOKENS = 32


class AnthropicProvider:
    def __init__(
        self,
        model: str = "claude-haiku-5-5",
        *,
        max_cost_usd: float,
        max_tokens: int = 256,
        price_in: float | None = None,
        price_out: float | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
        retries: int = 2,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if max_cost_usd <= 0:
            raise ValueError("max_cost_usd deve ser > 0 (teto obrigatório)")
        if price_in is None or price_out is None:
            if model not in PRICES_USD_PER_MTOK:
                raise ValueError(f"preço do modelo {model!r} desconhecido: informe price_in e price_out")
            price_in, price_out = PRICES_USD_PER_MTOK[model]
        self.api_key = api_key if api_key is not None else os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.api_key:
            raise ProviderError("ANTHROPIC_API_KEY ausente no ambiente")
        self.model = model
        self.max_cost_usd, self.max_tokens = max_cost_usd, max_tokens
        self.price_in, self.price_out = price_in, price_out
        self.base_url = (base_url or os.environ.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com").rstrip("/")
        self.timeout, self.retries, self._sleep = timeout, retries, sleep
        self.spent_usd = 0.0  # gasto confirmado + reservas em voo
        self._lock = threading.Lock()

    def _cost(self, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens * self.price_in + output_tokens * self.price_out) / 1_000_000

    @staticmethod
    def _input_bound(prompt: str) -> int:
        # cada byte vira no máximo 1 token (chars/4 NÃO é limite: o tokenizer novo gera ~30% mais)
        return len(prompt.encode("utf-8")) + PROMPT_OVERHEAD_TOKENS

    def worst_case_usd(self, prompt: str) -> float:
        return self._cost(self._input_bound(prompt), self.max_tokens)

    def _reserve(self, prompt: str) -> float:
        if self._input_bound(prompt) > PRICE_TIER_LIMIT_TOKENS:
            raise ProviderError("prompt pode passar de 100k tokens: o preço muda e não é suportado")
        worst = self.worst_case_usd(prompt)
        with self._lock:  # checar e reservar é atômico: requisições concorrentes não furam o teto
            if self.spent_usd + worst > self.max_cost_usd:
                raise BudgetExceeded(
                    f"gasto US$ {self.spent_usd:.6f} + pior caso US$ {worst:.6f} > teto US$ {self.max_cost_usd:.6f}"
                )
            self.spent_usd += worst
        return worst

    def _settle(self, reserved: float, actual: float) -> None:
        with self._lock:
            self.spent_usd += actual - reserved

    def _request(self, prompt: str) -> urllib.request.Request:
        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "thinking": {"type": "disabled"},  # thinking é cobrado como saída: fora do teto previsível
            "messages": [{"role": "user", "content": prompt}],
        }
        return urllib.request.Request(
            f"{self.base_url}/v1/messages",
            data=json.dumps(body).encode("utf-8"),
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            method="POST",
        )

    def generate(self, prompt: str) -> Generation:
        attempt = 0
        while True:
            reserved = self._reserve(prompt)  # a cada tentativa, inclusive retry
            wait = 0.5 * 2**attempt
            try:
                with urllib.request.urlopen(self._request(prompt), timeout=self.timeout) as resp:
                    raw = resp.read()
            except urllib.error.HTTPError as e:
                self._settle(reserved, 0.0)  # erro HTTP com status = não cobrado
                if e.code not in RETRYABLE_STATUS:
                    raise ProviderError(f"HTTP {e.code} da API") from None
                ra = e.headers.get("retry-after")
                if ra and ra.replace(".", "", 1).isdigit():
                    wait = float(ra)
                err = f"HTTP {e.code} da API"
            except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
                if isinstance(getattr(e, "reason", e), NOT_SENT):
                    self._settle(reserved, 0.0)
                # senão: pode ter chegado e sido cobrado sem sabermos => a reserva (pior caso) fica
                err = f"falha de rede: {type(e).__name__}"
            else:
                return self._parse(raw, reserved)
            if attempt >= self.retries:
                raise ProviderError(f"{err} após {attempt + 1} tentativas")
            self._sleep(min(wait, 8.0))
            attempt += 1

    def _parse(self, raw: bytes, reserved: float) -> Generation:
        try:
            data = json.loads(raw)
            in_tok, out_tok = int(data["usage"]["input_tokens"]), int(data["usage"]["output_tokens"])
            text = "".join(b["text"] for b in data["content"] if b.get("type") == "text")
        except (ValueError, KeyError, TypeError):
            raise ProviderError("resposta inesperada da API") from None  # cobrada: reserva fica
        self._settle(reserved, self._cost(in_tok, out_tok))
        return Generation(text, self.model, in_tok, out_tok)


def get_provider():
    name = os.getenv("LLM_PROVIDER", "fixture").lower()
    if name == "fixture":
        return FixtureProvider()
    if name == "anthropic":
        raw = os.getenv("LLM_MAX_COST_USD", "")
        try:
            teto = float(raw)
        except ValueError:
            teto = 0.0
        if teto <= 0:
            raise ValueError("LLM_PROVIDER=anthropic exige LLM_MAX_COST_USD > 0 (sem teto não sobe)")
        pin, pout = os.getenv("LLM_PRICE_IN"), os.getenv("LLM_PRICE_OUT")
        return AnthropicProvider(
            os.getenv("LLM_MODEL", "claude-haiku-5-5"),
            max_cost_usd=teto,
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "256")),
            price_in=float(pin) if pin else None,
            price_out=float(pout) if pout else None,
        )
    raise ValueError(f"LLM_PROVIDER desconhecido: {name!r} (use fixture ou anthropic)")
