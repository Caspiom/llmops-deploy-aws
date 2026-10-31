"""Providers de LLM. Hello-world usa o provider `fixture` (offline, grátis,
determinístico) para o esqueleto rodar sem chave de API e sem custo. Providers
reais entram atrás da env LLM_PROVIDER, sem quebrar o fluxo grátis."""
from __future__ import annotations
import hashlib
import os
import time
from dataclasses import dataclass


@dataclass
class Generation:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int


def _count_tokens(s: str) -> int:
    # Aproximação barata (~4 chars/token). Suficiente p/ observabilidade de custo.
    return max(1, len(s) // 4)


class FixtureProvider:
    """LLM falso, determinístico e offline. Latência simulada pequena para que
    as métricas de latência tenham um número real de verdade no histograma."""

    model = "fixture-1"

    def generate(self, prompt: str) -> Generation:
        time.sleep(0.015)  # simula custo de inferência (~15ms)
        h = hashlib.sha256(prompt.encode()).hexdigest()[:8]
        text = f"[fixture] eco de {len(prompt)} chars (hash {h})"
        return Generation(
            text=text,
            model=self.model,
            prompt_tokens=_count_tokens(prompt),
            completion_tokens=_count_tokens(text),
        )


class _RealProviderNotConfigured:
    """Placeholder: providers reais (OpenAI/Bedrock/Anthropic) entram aqui.
    Mantido como stub para NÃO gastar nem exigir chave no hello-world."""

    def __init__(self, name: str):
        self.name = name

    def generate(self, prompt: str) -> Generation:  # pragma: no cover
        raise NotImplementedError(
            f"Provider '{self.name}' ainda não implementado. "
            "Hello-world roda com LLM_PROVIDER=fixture (grátis). "
            "Providers reais entram numa próxima sessão, com teto de custo."
        )


def get_provider():
    name = os.getenv("LLM_PROVIDER", "fixture").lower()
    if name == "fixture":
        return FixtureProvider()
    return _RealProviderNotConfigured(name)
