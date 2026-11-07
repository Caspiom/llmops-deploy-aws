import threading

import pytest
from fake_anthropic import FakeAnthropic, err, ok
from fastapi.testclient import TestClient

import src.app as appmod
from src.providers import AnthropicProvider, BudgetExceeded, ProviderError, get_provider

KEY = "sk-ant-TESTE-nao-vazar"
PIN, POUT = 0.10, 0.50


def prov(srv, **kw):
    kw.setdefault("max_cost_usd", 1.0)
    return AnthropicProvider(api_key=KEY, base_url=srv.url, sleep=lambda s: None, **kw)


def test_resposta_usage_e_custo_exato():
    with FakeAnthropic(ok("Brasília", in_tok=1000, out_tok=200)) as srv:
        p = prov(srv)
        g = p.generate("oi")
    assert (g.text, g.model, g.prompt_tokens, g.completion_tokens) == ("Brasília", "claude-haiku-5-5", 1000, 200)
    assert p.spent_usd == pytest.approx((1000 * PIN + 200 * POUT) / 1e6)  # reserva ajustada ao custo real


def test_formato_da_requisicao():
    with FakeAnthropic() as srv:
        prov(srv, max_tokens=77).generate("pergunta")
    (r,) = srv.requests
    assert r["path"] == "/v1/messages" and r["headers"]["x-api-key"] == KEY
    b = r["body"]
    assert b["max_tokens"] == 77 and b["thinking"] == {"type": "disabled"}
    assert b["messages"] == [{"role": "user", "content": "pergunta"}]


def test_so_blocos_de_texto_entram_na_resposta():
    blocos = [{"type": "thinking", "thinking": "SEGREDO-DE-RACIOCINIO"}, {"type": "text", "text": "A"},
              {"type": "text", "text": "B"}]
    with FakeAnthropic(ok(content=blocos)) as srv:
        assert prov(srv).generate("x").text == "AB"


def test_pior_caso_calculado_a_mao():
    with FakeAnthropic() as srv:
        # (2 bytes + 32) * 0,10 + 256 * 0,50 = 131,4 US$/1e6
        assert prov(srv, max_tokens=256).worst_case_usd("oi") == pytest.approx(131.4e-6)


def test_teto_menor_que_o_pior_caso_nao_chama_o_modelo():
    with FakeAnthropic() as srv:
        p = prov(srv, max_cost_usd=130e-6)
        with pytest.raises(BudgetExceeded):
            p.generate("oi")
    assert srv.requests == [] and p.spent_usd == 0.0


def test_teto_igual_ao_pior_caso_ainda_chama():
    with FakeAnthropic(ok(in_tok=1, out_tok=1)) as srv:
        p = prov(srv)
        p.max_cost_usd = p.worst_case_usd("oi")  # fronteira EXATA: gasto + pior == teto => permitido
        assert p.generate("oi").text == "42"
    assert len(srv.requests) == 1


def test_gasto_nunca_passa_do_teto_no_pior_caso():
    with FakeAnthropic(ok(in_tok=34, out_tok=256)) as srv:  # servidor gasta o máximo por chamada
        p = prov(srv, max_cost_usd=131.4e-6 * 2.5)
        feitas = 0
        for _ in range(5):
            try:
                p.generate("oi")
                feitas += 1
            except BudgetExceeded:
                break
            assert p.spent_usd <= p.max_cost_usd + 1e-12
    assert feitas == 2 and len(srv.requests) == 2


def test_concorrencia_nao_fura_o_teto():
    """20 threads com teto para 3 chamadas: no máximo 3 chegam ao modelo."""
    with FakeAnthropic({**ok(in_tok=34, out_tok=256), "delay": 0.2}) as srv:
        p = prov(srv, max_cost_usd=131.4e-6 * 3.5)
        res = []
        def w():
            try:
                p.generate("oi"); res.append("ok")
            except BudgetExceeded:
                res.append("barrado")
        ts = [threading.Thread(target=w) for _ in range(20)]
        [t.start() for t in ts]; [t.join() for t in ts]
    assert res.count("ok") == 3 and res.count("barrado") == 17 and len(srv.requests) == 3
    assert p.spent_usd <= p.max_cost_usd


def test_retry_429_respeita_retry_after():
    esperas = []
    with FakeAnthropic(err(429, {"retry-after": "3"}), err(529), ok("ok")) as srv:
        p = AnthropicProvider(api_key=KEY, base_url=srv.url, max_cost_usd=1.0, sleep=esperas.append)
        assert p.generate("x").text == "ok"
    assert len(srv.requests) == 3 and esperas == [3.0, 1.0]


def test_retries_esgotados_nao_cobram_e_limitam_tentativas():
    with FakeAnthropic(err(503)) as srv:
        p = prov(srv, retries=2)
        with pytest.raises(ProviderError):
            p.generate("x")
    assert len(srv.requests) == 3 and p.spent_usd == 0.0


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_erro_de_cliente_nao_repete_e_nao_cobra(status):
    with FakeAnthropic(err(status)) as srv:
        p = prov(srv)
        with pytest.raises(ProviderError):
            p.generate("x")
    assert len(srv.requests) == 1 and p.spent_usd == 0.0


def test_timeout_mantem_a_reserva_do_pior_caso_e_o_teto_barra_o_retry():
    with FakeAnthropic({**ok(), "delay": 0.6}) as srv:
        p = AnthropicProvider(api_key=KEY, base_url=srv.url, timeout=0.15, max_cost_usd=131.4e-6 * 1.5,
                              sleep=lambda s: None)
        with pytest.raises(BudgetExceeded):
            p.generate("x" if False else "oi")
    assert p.spent_usd == pytest.approx(131.4e-6) and len(srv.requests) == 1


def test_resposta_malformada_mantem_a_reserva():
    with FakeAnthropic({"status": 200, "body": b"nao-e-json"}) as srv:
        p = prov(srv)
        with pytest.raises(ProviderError):
            p.generate("oi")
    assert p.spent_usd == pytest.approx(131.4e-6)


def test_prompt_gigante_recusado():
    with FakeAnthropic() as srv:
        with pytest.raises(ProviderError):
            prov(srv).generate("x" * 100_001)
    assert srv.requests == []


def test_config_sem_teto_nao_sobe(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    monkeypatch.delenv("LLM_MAX_COST_USD", raising=False)
    with pytest.raises(ValueError):
        get_provider()
    monkeypatch.setenv("LLM_MAX_COST_USD", "0")
    with pytest.raises(ValueError):
        get_provider()


def test_config_sem_chave_ou_provider_desconhecido_nao_sobe(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MAX_COST_USD", "0.05")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ProviderError):
        get_provider()
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    with pytest.raises(ValueError):
        get_provider()


def test_config_valida_le_o_ambiente(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MAX_COST_USD", "0.05")
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    monkeypatch.setenv("LLM_MAX_TOKENS", "64")
    p = get_provider()
    assert (p.max_cost_usd, p.max_tokens, p.model) == (0.05, 64, "claude-haiku-5-5")


# ---- ponta a ponta pela API HTTP do serviço ----
def _client(monkeypatch, srv, teto):
    monkeypatch.setattr(appmod, "_provider", prov(srv, max_cost_usd=teto))
    return TestClient(appmod.app)


def test_generate_usa_tokens_reais_e_custo_real(monkeypatch):
    with FakeAnthropic(ok("oi!", in_tok=100, out_tok=10)) as srv:
        r = _client(monkeypatch, srv, 1.0).post("/generate", json={"prompt": "ola"})
    b = r.json()
    assert r.status_code == 200 and b["model"] == "claude-haiku-5-5" and b["text"] == "oi!"
    assert b["usage"] == {"prompt_tokens": 100, "completion_tokens": 10}
    assert b["estimated_cost_usd"] == pytest.approx((100 * PIN + 10 * POUT) / 1e6)
    import re
    with FakeAnthropic(ok("oi!", in_tok=100, out_tok=10)) as srv:
        c = _client(monkeypatch, srv, 0.5)
        c.post("/generate", json={"prompt": "ola"})
        m = c.get("/metrics").text
    spent = float(re.search(r"^llmops_budget_spent_usd (\S+)", m, re.M).group(1))
    assert spent == pytest.approx((100 * PIN + 10 * POUT) / 1e6)  # gasto real, não a reserva


def test_generate_429_quando_estoura_o_teto_e_expoe_metrica(monkeypatch):
    with FakeAnthropic() as srv:
        c = _client(monkeypatch, srv, 1e-9)
        r = c.post("/generate", json={"prompt": "ola"})
        m = c.get("/metrics").text
    import re
    assert r.status_code == 429 and srv.requests == []
    n = float(re.search(r"^llmops_budget_rejected_total (\S+)", m, re.M).group(1))
    assert n >= 1 and "llmops_budget_spent_usd" in m
    assert KEY not in r.text and KEY not in m


def test_generate_502_sem_vazar_detalhes_nem_chave(monkeypatch):
    with FakeAnthropic(err(401)) as srv:
        r = _client(monkeypatch, srv, 1.0).post("/generate", json={"prompt": "ola"})
    assert r.status_code == 502 and KEY not in r.text and "401" not in r.text
