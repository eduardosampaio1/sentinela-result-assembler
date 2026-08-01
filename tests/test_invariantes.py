"""Invariantes — um teste por regra, cada um mudando UM campo da massa válida.

Mudar um campo só é deliberado: se o teste montasse um payload próprio, ele passaria a
provar aquele payload. Partindo de uma massa que comprovadamente monta, a única
explicação para a recusa é a regra sob teste.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from result_assembler import (
    AnalysisFacts,
    AssemblyInvariantViolation,
    DuplicateIndicator,
    InvalidDenominator,
    InvalidUnit,
    InvalidValue,
    MissingRequiredFact,
    UnknownIndicator,
    UnsupportedFactsVersion,
    UnsupportedMeasurementVersion,
    assemble,
)

from massas import carregar_json, com_indicador, indice_de


@pytest.fixture
def bruto() -> dict:
    return carregar_json("massa_a_principal.facts.json")


def montar(payload: dict) -> None:
    assemble(AnalysisFacts.model_validate(payload))


class TestVersoes:
    def test_facts_schema_desconhecido_recusa(self, bruto):
        bruto["facts_schema_version"] = "analysis-facts-v99"
        with pytest.raises(UnsupportedFactsVersion):
            montar(bruto)

    def test_measurement_contract_desconhecido_recusa(self, massa_e_json):
        with pytest.raises(UnsupportedMeasurementVersion):
            montar(massa_e_json)

    def test_calculation_version_invalida(self, bruto):
        with pytest.raises(UnsupportedMeasurementVersion):
            montar(com_indicador(bruto, calculation_version="9.9"))


class TestIdentidade:
    def test_analysis_id_vazio_recusa(self, bruto):
        bruto["identity"]["analysis_id"] = "   "
        with pytest.raises(MissingRequiredFact):
            montar(bruto)

    def test_analyzed_at_vazio_recusa(self, bruto):
        bruto["window"]["analyzed_at"] = "  "
        with pytest.raises(MissingRequiredFact):
            montar(bruto)


class TestIndicadores:
    def test_id_duplicado_recusa(self, bruto):
        bruto["indicators"].append(dict(bruto["indicators"][0]))
        with pytest.raises(DuplicateIndicator):
            montar(bruto)

    def test_indicador_desconhecido_recusa_fail_closed(self, bruto):
        with pytest.raises(UnknownIndicator):
            montar(com_indicador(bruto, id="metrica_que_alguem_inventou"))

    def test_kind_incompativel_recusa(self, bruto):
        with pytest.raises(InvalidValue):
            montar(com_indicador(bruto, kind="count"))

    def test_unidade_incompativel_recusa(self, bruto):
        with pytest.raises(InvalidUnit):
            montar(com_indicador(bruto, unit="percent"))

    def test_source_nao_aceita_recusa(self, bruto):
        with pytest.raises(InvalidValue):
            montar(com_indicador(bruto, source="algum.modulo.improvisado"))

    def test_razao_fora_da_faixa_recusa(self, bruto):
        with pytest.raises(InvalidValue):
            montar(com_indicador(bruto, value=1.4))

    def test_contagem_negativa_recusa(self, bruto):
        idx = indice_de(bruto, "useful_outcomes")
        bruto["indicators"][idx]["value"] = -1
        with pytest.raises(InvalidValue):
            montar(bruto)

    def test_contagem_fracionaria_recusa(self, bruto):
        idx = indice_de(bruto, "useful_outcomes")
        bruto["indicators"][idx]["value"] = 80.5
        with pytest.raises(InvalidValue):
            montar(bruto)

    def test_nan_recusa_no_modelo(self, bruto):
        with pytest.raises(ValidationError):
            AnalysisFacts.model_validate(com_indicador(bruto, value=float("nan")))

    def test_infinito_recusa_no_modelo(self, bruto):
        with pytest.raises(ValidationError):
            AnalysisFacts.model_validate(com_indicador(bruto, value=float("inf")))

    def test_bool_nao_e_medicao(self, bruto):
        # `True` viraria 1.0 na coerção do pydantic e passaria como razão válida.
        with pytest.raises(ValidationError):
            AnalysisFacts.model_validate(com_indicador(bruto, value=True))

    def test_campo_extra_nao_contratado_recusa(self, bruto):
        with pytest.raises(ValidationError):
            AnalysisFacts.model_validate(com_indicador(bruto, campo_novo_do_dominio=1))


class TestDenominadorEMoeda:
    def test_denominador_obrigatorio_ausente_recusa(self, bruto):
        with pytest.raises(InvalidDenominator):
            montar(com_indicador(bruto, denominator=None))

    def test_denominador_de_tipo_errado_recusa(self, bruto):
        with pytest.raises(InvalidDenominator):
            montar(com_indicador(bruto, denominator={"kind": "intents", "value": 20}))

    def test_denominador_em_indicador_que_nao_contrata_recusa(self, bruto):
        idx = indice_de(bruto, "useful_outcomes")
        bruto["indicators"][idx]["denominator"] = {"kind": "analyzed_conversations", "value": 100}
        with pytest.raises(InvalidDenominator):
            montar(bruto)

    def test_denominador_zero_recusa_no_modelo(self, bruto):
        with pytest.raises(ValidationError):
            AnalysisFacts.model_validate(
                com_indicador(bruto, denominator={"kind": "analyzed_conversations", "value": 0})
            )

    def test_moeda_sem_codigo_recusa(self, bruto):
        idx = indice_de(bruto, "total_estimated_cost")
        bruto["indicators"][idx]["currency"] = None
        with pytest.raises(InvalidUnit):
            montar(bruto)

    def test_codigo_de_moeda_invalido_recusa(self, bruto):
        idx = indice_de(bruto, "total_estimated_cost")
        bruto["indicators"][idx]["currency"] = "dolar"
        with pytest.raises(InvalidUnit):
            montar(bruto)


class TestCoerenciaDisponibilidade:
    def test_available_sem_valor_recusa(self, bruto):
        with pytest.raises(AssemblyInvariantViolation):
            montar(com_indicador(bruto, value=None))

    def test_ausencia_com_valor_zero_recusa(self, bruto):
        """O defeito com nome: `unavailable` carregando 0.0. Um consumidor leria zero."""
        with pytest.raises(AssemblyInvariantViolation) as exc:
            montar(
                com_indicador(
                    bruto, availability="unavailable", reason="no_input_data", value=0.0
                )
            )
        assert "ausência" in str(exc.value).lower()

    def test_indisponivel_com_motivo_ok_recusa(self, bruto):
        with pytest.raises(AssemblyInvariantViolation):
            montar(com_indicador(bruto, availability="unavailable", reason="ok", value=None))

    def test_partial_sem_cobertura_recusa(self, bruto):
        with pytest.raises(AssemblyInvariantViolation):
            montar(com_indicador(bruto, availability="partial", reason="missing_dimension"))

    def test_partial_com_cobertura_1_recusa(self, bruto):
        with pytest.raises(AssemblyInvariantViolation):
            montar(
                com_indicador(
                    bruto,
                    availability="partial",
                    reason="missing_dimension",
                    data_coverage=1.0,
                )
            )


class TestRecomendacoesEEvidencias:
    def test_recomendacao_duplicada_recusa(self, massa_f):
        bruto = carregar_json("massa_f_recomendacoes_evidencias.facts.json")
        bruto["recommendations"].append(dict(bruto["recommendations"][0], order=99))
        with pytest.raises(AssemblyInvariantViolation):
            montar(bruto)

    def test_ordem_duplicada_recusa(self):
        bruto = carregar_json("massa_f_recomendacoes_evidencias.facts.json")
        bruto["recommendations"][0]["order"] = bruto["recommendations"][1]["order"]
        with pytest.raises(AssemblyInvariantViolation):
            montar(bruto)

    def test_prioridade_vazia_recusa(self):
        bruto = carregar_json("massa_f_recomendacoes_evidencias.facts.json")
        with pytest.raises(ValidationError):
            AnalysisFacts.model_validate(
                {**bruto, "recommendations": [{**bruto["recommendations"][0], "priority": ""}]}
            )

    def test_evidence_ref_orfa_recusa(self):
        bruto = carregar_json("massa_f_recomendacoes_evidencias.facts.json")
        bruto["recommendations"][0]["evidence_refs"] = ["ev-inexistente"]
        with pytest.raises(AssemblyInvariantViolation):
            montar(bruto)

    def test_evidencia_duplicada_recusa(self):
        bruto = carregar_json("massa_f_recomendacoes_evidencias.facts.json")
        bruto["evidence"].append(dict(bruto["evidence"][0]))
        with pytest.raises(AssemblyInvariantViolation):
            montar(bruto)


class TestDimensoes:
    def test_dimensao_desconhecida_recusa(self, bruto):
        bruto["dimensions"] = [
            {
                "id": "dimensao_inventada",
                "availability": "available",
                "reason": "ok",
                "value": 0.5,
                "data_coverage": None,
                "calculation_version": "1.0",
                "source": "core._engine_helpers.build_ai_health_measurement",
            }
        ]
        with pytest.raises(UnknownIndicator):
            montar(bruto)
