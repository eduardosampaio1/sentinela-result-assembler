"""Invariantes acrescentados pela revisão de semântica analítica (Codex R1).

Três achados procedentes, três regras, um teste por consequência concreta.
"""

from __future__ import annotations

from typing import Any

import pytest

from massas import carregar_json, com_indicador
from result_assembler import (
    AnalysisFacts,
    AssemblyInvariantViolation,
    DuplicateIndicator,
    InvalidUnit,
    SchemaMismatch,
    UnknownIndicator,
    UnsupportedMeasurementVersion,
    assemble,
    parse_facts,
)

_HEALTH = "core._engine_helpers.build_ai_health_measurement"
_TENANT = "engine.business.unit_economics.compute_tenant_metrics"


@pytest.fixture
def bruto() -> dict[str, Any]:
    return carregar_json("massa_a_principal.facts.json")


def montar(payload: dict[str, Any]) -> None:
    assemble(AnalysisFacts.model_validate(payload))


def com_dimensao(bruto: dict[str, Any], **campos: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "economic",
        "availability": "available",
        "reason": "ok",
        "value": 0.72,
        "data_coverage": None,
        "calculation_version": "1.0",
        "source": _HEALTH,
    }
    base.update(campos)
    return {**bruto, "dimensions": [base]}


class TestDimensoesPassamPelaMesmaRegua:
    """Codex R1 [1] — dimensões não passavam por régua nenhuma.

    O caminho estava aberto: `FactDimension` tem disponibilidade, valor, cobertura e
    versão de cálculo, o resultado público PUBLICA dimensão com estado e valor, e nada
    conferia a coerência entre os dois. O mesmo defeito que os indicadores bloqueavam
    entrava pela porta ao lado.
    """

    def test_dimensao_valida_monta(self, bruto):
        montar(com_dimensao(bruto))

    def test_ausencia_com_valor_recusa(self, bruto):
        """Cenário exato do achado: `unavailable` carregando 0.72 seria publicado como
        `not_measured` com valor presente."""
        with pytest.raises(AssemblyInvariantViolation):
            montar(
                com_dimensao(bruto, availability="unavailable", reason="no_input_data", value=0.72)
            )

    def test_versao_de_calculo_desconhecida_recusa(self, bruto):
        with pytest.raises(UnsupportedMeasurementVersion):
            montar(com_dimensao(bruto, calculation_version="9.9"))

    def test_available_sem_valor_recusa(self, bruto):
        with pytest.raises(AssemblyInvariantViolation):
            montar(com_dimensao(bruto, value=None))

    def test_valor_fora_de_zero_um_recusa(self, bruto):
        """A faixa 0..1 da dimensão migrou para o Field — e daí para o JSON Schema
        publicado (Codex R2 [3]). A recusa acontece uma camada antes, e `parse_facts`
        a entrega como `SchemaMismatch`, da família da biblioteca."""
        with pytest.raises(SchemaMismatch):
            parse_facts(com_dimensao(bruto, value=1.4))

    def test_partial_sem_cobertura_recusa(self, bruto):
        with pytest.raises(AssemblyInvariantViolation):
            montar(com_dimensao(bruto, availability="partial", reason="missing_dimension"))

    def test_indisponivel_com_motivo_ok_recusa(self, bruto):
        with pytest.raises(AssemblyInvariantViolation):
            montar(com_dimensao(bruto, availability="unavailable", reason="ok", value=None))

    def test_dimensao_duplicada_recusa(self, bruto):
        payload = com_dimensao(bruto)
        payload["dimensions"].append(dict(payload["dimensions"][0]))
        with pytest.raises(DuplicateIndicator):
            montar(payload)

    def test_dimensao_desconhecida_recusa(self, bruto):
        with pytest.raises(UnknownIndicator):
            montar(com_dimensao(bruto, id="dimensao_inventada"))


class TestUnidadeObrigatoria:
    """Codex R1 [2] — unidade omitida passava como se tivesse sido confirmada."""

    def test_unidade_ausente_quando_contratada_recusa(self, bruto):
        with pytest.raises(InvalidUnit):
            montar(com_indicador(bruto, unit=None))

    def test_unidade_declarada_onde_o_contrato_nao_tem_recusa(self, bruto):
        """`mean_response_variance_per_intent` é escalar puro. Declarar "ratio" ali
        inventaria uma unidade que o domínio não mediu."""
        with pytest.raises(InvalidUnit):
            montar(
                com_indicador(
                    bruto,
                    id="avg_variance_per_intent",
                    kind="scalar",
                    unit="ratio",
                    value=0.3,
                    denominator=None,
                    source=_TENANT,
                )
            )

    def test_escalar_sem_unidade_monta(self, bruto):
        montar(
            com_indicador(
                bruto,
                id="avg_variance_per_intent",
                kind="scalar",
                unit=None,
                value=0.3,
                denominator=None,
                source=_TENANT,
            )
        )


class TestContadoresCoerentesComACobertura:
    """Codex R1 [3] — os contadores podiam desmentir a cobertura publicada."""

    def test_cobertura_incoerente_recusa(self, bruto):
        with pytest.raises(AssemblyInvariantViolation) as exc:
            montar(
                com_indicador(
                    bruto,
                    availability="partial",
                    reason="missing_dimension",
                    data_coverage=0.5,
                    observed_units=25,
                    expected_units=1000,
                )
            )
        assert "data_coverage" in str(exc.value)

    def test_observado_maior_que_esperado_recusa(self, bruto):
        with pytest.raises(AssemblyInvariantViolation):
            montar(com_indicador(bruto, observed_units=60, expected_units=50))

    def test_esperado_zero_recusa(self, bruto):
        """`expected_units > 0` também virou restrição do Field."""
        with pytest.raises(SchemaMismatch):
            parse_facts(com_indicador(bruto, observed_units=0, expected_units=0))

    def test_contadores_coerentes_montam(self, bruto):
        montar(
            com_indicador(
                bruto,
                availability="partial",
                reason="missing_dimension",
                data_coverage=0.5,
                observed_units=25,
                expected_units=50,
            )
        )
