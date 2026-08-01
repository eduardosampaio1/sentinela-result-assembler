"""Montagem: estados, parcialidade, ordem e manifesto."""

from __future__ import annotations

import json
import pathlib

import pytest

from result_assembler import (
    ASSEMBLER_VERSION,
    INDICATOR_REGISTRY_VERSION,
    IndicatorState,
    assemble,
    to_canonical_dict,
    validate_result,
)

DOURADOS = pathlib.Path(__file__).resolve().parent / "golden"


def _estados(resultado) -> dict[str, IndicatorState]:
    return {i.id: i.state for i in resultado.indicators}


class TestEstadosPublicos:
    def test_cinco_estados_de_disponibilidade_mapeiam_um_a_um(self, massa_d):
        """A massa D traz os cinco estados num documento só. Se dois colapsassem, o
        consumidor perderia a diferença entre "não medido" e "falhou ao calcular"."""
        e = _estados(assemble(massa_d).public_result)
        assert e["useful_outcome_rate"] is IndicatorState.MEASURED
        assert e["intent_coverage_rate"] is IndicatorState.PARTIALLY_MEASURED
        assert e["cost_per_useful_outcome"] is IndicatorState.NOT_MEASURED
        assert e["conversion_rate"] is IndicatorState.NOT_APPLICABLE
        assert e["mean_response_variance_per_intent"] is IndicatorState.CALCULATION_FAILED
        assert len(set(e.values())) == 5

    def test_cobertura_so_aparece_no_parcial(self, massa_d):
        r = assemble(massa_d).public_result
        por_id = {i.id: i for i in r.indicators}
        assert por_id["intent_coverage_rate"].coverage == 0.5
        # Publicar cobertura num indicador completo sugeriria uma limitação que não existe.
        assert por_id["useful_outcome_rate"].coverage is None
        assert por_id["cost_per_useful_outcome"].coverage is None


class TestParcialidade:
    def test_massa_completa_declara_completo(self, massa_a):
        p = assemble(massa_a).public_result.partiality
        assert p.complete is True
        assert p.reasons == ()

    def test_massa_parcial_declara_os_motivos_ordenados(self, massa_d):
        p = assemble(massa_d).public_result.partiality
        assert p.complete is False
        assert p.reasons == (
            "indicator_calculation_failed",
            "indicator_not_applicable",
            "indicator_not_measured",
            "indicator_partially_measured",
        )
        assert list(p.reasons) == sorted(p.reasons)

    def test_zero_real_nao_torna_o_resultado_parcial(self, massa_b):
        """Massa B tem zeros reais E um não medido. O que quebra `complete` é o não
        medido — zero medido é medição."""
        p = assemble(massa_b).public_result.partiality
        assert p.complete is False
        assert p.reasons == ("indicator_not_measured",)


class TestOrdem:
    def test_indicadores_saem_na_ordem_canonica_do_registro(self, massa_a):
        from result_assembler import CANONICAL_ORDER, INDICATOR_REGISTRY

        r = assemble(massa_a).public_result
        esperado = [
            INDICATOR_REGISTRY[i].public_id
            for i in CANONICAL_ORDER
            if i in {x.id for x in massa_a.indicators}
        ]
        assert [i.id for i in r.indicators] == esperado

    def test_recomendacoes_saem_na_ordem_do_dominio(self, massa_f):
        """O payload traz rec-c, rec-a, rec-b. A ordem publicada vem do campo `order`
        (0,1,2), que o domínio já decidiu — o assembler não reordena por impacto."""
        r = assemble(massa_f).public_result
        assert [x.id for x in r.recommendations] == ["rec-a", "rec-b", "rec-c"]
        assert [x.priority for x in r.recommendations] == ["P1", "P2", "P3"]

    def test_assembler_nao_elege_recomendacao_principal(self, massa_f):
        """Nenhum campo do contrato público marca "a principal". Se existisse, alguém
        teria que escolher — e essa escolha é do domínio."""
        from result_assembler.contracts.result import PublicRecommendation

        campos = set(PublicRecommendation.model_fields)
        assert not campos & {"primary", "headline", "is_main", "rank", "impact"}

    def test_evidencias_saem_ordenadas_por_id(self, massa_f):
        r = assemble(massa_f).public_result
        assert [e.id for e in r.evidence] == ["ev-1", "ev-2"]


class TestManifesto:
    def test_manifesto_declara_as_cinco_versoes(self, massa_a):
        v = assemble(massa_a).internal_manifest.versions
        assert v.assembler_version == ASSEMBLER_VERSION
        assert v.facts_schema_version == "analysis-facts-v1"
        assert v.result_schema_version == "analysis-result-v1"
        assert v.measurement_contract_version == "measurement-1.0"
        assert v.indicator_registry_version == INDICATOR_REGISTRY_VERSION

    def test_aceitos_batem_com_o_publicado(self, massa_a):
        o = assemble(massa_a)
        assert o.internal_manifest.accepted_indicator_ids == tuple(
            i.id for i in o.public_result.indicators
        )

    def test_avisos_sao_ordenados_e_honestos(self, massa_a):
        a = assemble(massa_a).internal_manifest.warnings
        assert "no_recommendations_published" in a
        assert "no_evidence_published" in a
        assert "result_is_partial" not in a
        assert list(a) == sorted(a)


class TestRevalidacao:
    def test_resultado_montado_revalida(self, massa_d):
        validate_result(assemble(massa_d).public_result)

    def test_versao_publicada_e_a_do_pacote(self, massa_a):
        r = assemble(massa_a).public_result
        assert r.result_schema_version == "analysis-result-v1"
        # A versão de MEDIÇÃO é a que veio nos fatos — não é o assembler que a define.
        assert r.measurement_contract_version == massa_a.measurement_contract_version


class TestGolden:
    """Documentos dourados: o resultado inteiro, congelado.

    Um teste de campo isolado não pega adição acidental de campo nem mudança de ordem.
    O dourado pega — e obriga quem muda o contrato a olhar o diff.
    """

    @pytest.mark.parametrize(
        "fixture_nome,dourado",
        [
            ("massa_a", "massa_a_principal.result.json"),
            ("massa_b", "massa_b_zero_e_nao_medido.result.json"),
            ("massa_d", "massa_d_parcial.result.json"),
            ("massa_f", "massa_f_recomendacoes_evidencias.result.json"),
        ],
    )
    def test_resultado_bate_com_o_dourado(self, request, fixture_nome, dourado):
        facts = request.getfixturevalue(fixture_nome)
        obtido = to_canonical_dict(assemble(facts).public_result)
        esperado = json.loads((DOURADOS / dourado).read_text(encoding="utf-8"))
        assert obtido == esperado
