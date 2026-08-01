"""Semântica do que sai — as regressões que o discovery obriga a travar.

Cada teste aqui existe porque o comportamento errado JÁ ACONTECEU em algum lugar do
pipeline (frontend, adapter legado ou produtor), e não porque parecia uma boa ideia
testar.
"""

from __future__ import annotations

from result_assembler import IndicatorState, assemble


def _por_id(resultado, public_id: str):
    for i in resultado.indicators:
        if i.id == public_id:
            return i
    raise AssertionError(f"indicador ausente no resultado: {public_id}")


class TestRazaoNaoViraPercentual:
    def test_coverage_085_continua_085(self, massa_a):
        """A conversão para "85%" pertence ao frontend. Se o assembler multiplicasse por
        100, o frontend multiplicaria de novo e sairia 8.500%."""
        r = assemble(massa_a).public_result
        cov = _por_id(r, "outcome_field_coverage_rate")
        assert cov.value == 0.85
        assert cov.kind == "ratio"
        assert cov.unit == "ratio"

    def test_ratio_declara_denominador(self, massa_a):
        """0.85 sem "sobre o quê" é um número que ninguém consegue auditar."""
        cov = _por_id(assemble(massa_a).public_result, "outcome_field_coverage_rate")
        assert cov.denominator is not None
        assert cov.denominator.kind == "analyzed_conversations"
        assert cov.denominator.value == 100

    def test_dois_coverages_diferentes_tem_nomes_diferentes(self, massa_a):
        """`outcome_coverage` e `intent_coverage_rate` valem 0.85 na massa A — medido de
        verdade nos dois produtores. São COISAS DIFERENTES sobre denominadores
        diferentes, e o nome público precisa deixar isso óbvio."""
        r = assemble(massa_a).public_result
        outcome = _por_id(r, "outcome_field_coverage_rate")
        intent = _por_id(r, "intent_coverage_rate")
        assert outcome.value == intent.value == 0.85
        assert outcome.denominator.kind == "analyzed_conversations"
        assert intent.denominator.kind == "intents"


class TestContagemNuncaVirapercentual:
    def test_contagem_sai_como_contagem(self, massa_a):
        c = _por_id(assemble(massa_a).public_result, "analyzed_conversation_count")
        assert c.kind == "count"
        assert c.unit == "conversations"
        assert c.value == 100
        # Uma contagem não tem denominador; publicá-lo convidaria a virar razão.
        assert c.denominator is None
        assert c.display_precision == 0

    def test_handoff_count_e_zero_real_medido(self, massa_a):
        """Zero handoffs MEDIDOS. É `measured` com 0 — não é ausência."""
        h = _por_id(assemble(massa_a).public_result, "handoff_count")
        assert h.state is IndicatorState.MEASURED
        assert h.value == 0


class TestPrecisaoPreservada:
    def test_subcentavo_sobrevive(self, massa_c):
        """0.0042 não pode virar 0.00. O `display_precision` é sugestão; o valor sai
        exatamente como o domínio calculou."""
        r = assemble(massa_c).public_result
        assert _por_id(r, "total_estimated_cost").value == 0.0042
        assert _por_id(r, "cost_per_useful_outcome").value == 5e-06

    def test_serializacao_nao_perde_precisao(self, massa_c):
        from result_assembler import serialize_canonical

        bytes_ = serialize_canonical(assemble(massa_c).public_result)
        assert b"0.0042" in bytes_
        assert b"5e-06" in bytes_


class TestAusenciaNaoEZero:
    def test_zero_real_e_nao_medido_convivem(self, massa_b):
        """A massa B é o par crítico: `outcome_field_coverage_rate` é ZERO medido e
        `cost_per_useful_outcome` é NÃO MEDIDO. Colapsar os dois em 0.0 é o defeito que
        `core/adapters/argos.py` comete hoje."""
        r = assemble(massa_b).public_result
        zero = _por_id(r, "outcome_field_coverage_rate")
        ausente = _por_id(r, "cost_per_useful_outcome")

        assert zero.state is IndicatorState.MEASURED and zero.value == 0.0
        assert ausente.state is IndicatorState.NOT_MEASURED and ausente.value is None
        assert zero.state is not ausente.state

    def test_ausente_nao_declara_moeda(self, massa_b):
        """Sem valor não há moeda a declarar — declarar sugeriria um valor que não veio."""
        ausente = _por_id(assemble(massa_b).public_result, "cost_per_useful_outcome")
        assert ausente.currency is None


class TestDataVemDoDominio:
    def test_analyzed_at_e_o_do_fato(self, massa_a):
        """O assembler não tem relógio. Se tivesse, a data mentiria em toda remontagem."""
        r = assemble(massa_a).public_result
        assert r.summary.analyzed_at == massa_a.window.analyzed_at == "2026-07-31T10:00:00Z"

    def test_nenhum_modulo_do_pacote_importa_relogio_ou_aleatorio(self):
        """Cadeado estrutural: se alguém adicionar `datetime.now()` ou `random`, o teste
        acima continuaria passando (a massa traz a data) — este aqui não."""
        import ast
        import pathlib

        raiz = pathlib.Path(__file__).resolve().parent.parent / "src" / "result_assembler"
        proibidos = {"random", "time", "datetime", "secrets", "uuid", "os"}
        achados: list[str] = []
        for py in raiz.rglob("*.py"):
            arvore = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            for no in ast.walk(arvore):
                if isinstance(no, ast.Import):
                    achados += [
                        f"{py.name}: import {a.name}"
                        for a in no.names
                        if a.name.split(".")[0] in proibidos
                    ]
                elif isinstance(no, ast.ImportFrom) and no.module:
                    if no.module.split(".")[0] in proibidos:
                        achados.append(f"{py.name}: from {no.module}")
        assert achados == [], f"núcleo puro importou fonte de não-determinismo: {achados}"
