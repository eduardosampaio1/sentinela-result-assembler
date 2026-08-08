"""MF6.2 + MF6.3 — o documento INTEGRADO, e a reconciliação das contagens.

    Engine facts  +  Analytics public projection  →  analysis-result-v2

O que se prova aqui:

    o v1 NÃO se mexe            e há cadeado sobre isso
    wrapper obrigatório         conteúdo anulável; `withheld` nasce com `data: null`
    B == C é INVARIANTE          divergência RECUSA, nunca escolhe
    A ganha nome próprio        `engine_window_record_count`, e não há `record_count` no summary
    a projeção é TRANSPORTADA   nunca interpretada, nunca recalculada
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from massas import carregar, carregar_json
from result_assembler.assembler.assemble import assemble
from result_assembler.assembler.assemble_v2 import (
    RecordCountMismatch,
    _id_publico_das_conversas,
    assemble_v2,
)
from result_assembler.contracts.analytics import AnalyticsComponent, ComponentStatus
from result_assembler.contracts.facts import AnalysisFacts

PROJECAO = {"totais": {"conversas": 4}, "segmentos": []}


def _facts() -> AnalysisFacts:
    return carregar("massa_a_principal.facts.json")


def _conversas_dos_facts() -> int:
    """A contagem B como ela está na massa — lida do FATO, não adivinhada."""
    bruto = carregar_json("massa_a_principal.facts.json")
    for ind in bruto["indicators"]:
        if ind["id"] == "observed_conversations":
            return int(ind["value"])
    raise AssertionError("a massa não tem o indicador da contagem de conversas")


def _analytics(**campos: Any) -> AnalyticsComponent:
    base: dict[str, Any] = {
        "component_status": ComponentStatus.READY,
        "projection_digest": "d" * 64,
        "snapshot_contract_version": "analytics-snapshot-v1",
        "data": copy.deepcopy(PROJECAO),
        "record_count": _conversas_dos_facts(),
    }
    base.update(campos)
    return AnalyticsComponent(**base)


# ── o v1 não se mexe ────────────────────────────────────────────────────────


def test_o_v1_continua_EXATAMENTE_como_era() -> None:
    """**O cadeado da decisão de criar um v2.**

    `analysis-result-v1` tem `additionalProperties: false`: qualquer acréscimo — inclusive um
    campo opcional — é quebra para quem valida contra o schema publicado. O v2 existe para que o
    v1 não precise mudar, e este teste é o que impede a fatia de "aproveitar e" mexer nele.
    """
    v1 = assemble(_facts()).public_result

    assert v1.result_schema_version == "analysis-result-v1"
    assert hasattr(v1.summary, "record_count")
    assert not hasattr(v1, "analytics")


def test_os_dois_documentos_publicam_os_MESMOS_indicadores() -> None:
    """A montagem do v1 é reusada inteira. Reimplementá-la daria dois documentos que divergiriam
    no primeiro ajuste de ordenação, e cada `result_checksum` descreveria uma montagem
    diferente."""
    v1 = assemble(_facts()).public_result
    v2 = assemble_v2(_facts(), _analytics()).public_result

    assert [i.id for i in v2.indicators] == [i.id for i in v1.indicators]
    assert [i.state for i in v2.indicators] == [i.state for i in v1.indicators]
    assert v2.partiality == v1.partiality


# ── o bloco analítico ───────────────────────────────────────────────────────


def test_o_wrapper_e_OBRIGATORIO_e_leva_as_versoes_proprias() -> None:
    v2 = assemble_v2(_facts(), _analytics()).public_result

    assert v2.result_schema_version == "analysis-result-v2"
    assert v2.analytics.component_status is ComponentStatus.READY
    assert v2.analytics.projection_digest == "d" * 64
    # Versão PRÓPRIA: reusar a `measurement_contract_version` da Engine faria uma versão
    # descrever duas coisas que evoluem separadas.
    assert v2.analytics.snapshot_contract_version == "analytics-snapshot-v1"
    assert v2.measurement_contract_version != v2.analytics.snapshot_contract_version


def test_withheld_NASCE_com_data_null_e_nao_e_erro() -> None:
    """**A decisão da MF5, preservada.** Disclosure é conclusão, não defeito: o documento
    integrado nasce dizendo que nada foi liberado, em vez de morrer."""
    v2 = assemble_v2(
        _facts(),
        _analytics(component_status=ComponentStatus.WITHHELD, data=None, record_count=None),
    )

    assert v2.public_result.analytics.component_status is ComponentStatus.WITHHELD
    assert v2.public_result.analytics.data is None
    assert v2.public_result.analytics.record_count is None
    # E o resto do documento continua inteiro — a Engine não é apagada pela decisão analítica.
    assert v2.public_result.indicators
    # O manifesto DIZ por quê, para quem o lê não ter de inferir do `null`.
    assert "analytics_withheld" in v2.internal_manifest.warnings


def test_a_projecao_e_TRANSPORTADA_sem_interpretacao() -> None:
    """O Assembler não recalcula disclosure e não olha dentro do documento. Interpretar aqui
    seria decidir de novo o que o Privacy Gate já decidiu, num lugar sem os dados para isso."""
    v2 = assemble_v2(_facts(), _analytics()).public_result

    assert v2.analytics.data == PROJECAO


@pytest.mark.parametrize("estado", [ComponentStatus.READY, ComponentStatus.PARTIAL])
def test_declarar_conteudo_e_NAO_trazer_e_recusado(estado: ComponentStatus) -> None:
    """Um bloco que dissesse `ready` e viesse vazio publicaria "há resultado analítico" sobre
    nada — a mentira mais cara desta plataforma, porque parece confiável."""
    with pytest.raises(ValueError, match="sem conteúdo"):
        _analytics(component_status=estado, data=None)


def test_withheld_COM_conteudo_e_recusado() -> None:
    """O outro lado da mesma coerência: se há algo a liberar, o desfecho não é `withheld`."""
    with pytest.raises(ValueError, match="withheld com conteúdo"):
        _analytics(component_status=ComponentStatus.WITHHELD, data={"x": 1})


# ── MF6.3: as três contagens ────────────────────────────────────────────────


def test_A_ganha_nome_PROPRIO_e_o_summary_nao_tem_record_count() -> None:
    """**O ponto da MF6.3.** Com duas contagens no mesmo documento, um nome ambíguo faria a
    errada ser lida. `summary.record_count` do v1 não se mexe — ele continua lá, no v1."""
    v1 = assemble(_facts()).public_result
    v2 = assemble_v2(_facts(), _analytics()).public_result

    assert v2.summary.engine_window_record_count == v1.summary.record_count
    assert not hasattr(v2.summary, "record_count")
    assert "record_count" not in v2.summary.model_dump()


def test_B_e_C_iguais_MONTAM() -> None:
    """O controle. Sem ele, uma invariante que recusasse tudo também "provaria" rigor."""
    v2 = assemble_v2(_facts(), _analytics()).public_result

    assert v2.analytics.record_count == _conversas_dos_facts()


def test_B_diferente_de_C_RECUSA_a_montagem() -> None:
    """Publicar uma das duas seria escolher em silêncio qual fonte está certa, e a errada
    apareceria como número num painel."""
    with pytest.raises(RecordCountMismatch) as capturada:
        assemble_v2(_facts(), _analytics(record_count=_conversas_dos_facts() + 1))

    assert capturada.value.denominador == _conversas_dos_facts() + 1
    assert capturada.value.observadas == _conversas_dos_facts()


def test_A_e_C_NAO_sao_comparadas() -> None:
    """`A` é a janela da Engine; `C` é o denominador analítico. Compará-las recusaria montagens
    perfeitamente corretas — foi por confundir as duas que o v1 precisou de nome novo.

    O caso é CONSTRUÍDO, e não herdado da massa: nela A e B calham de ser iguais (100), e um
    teste que dependesse disso não estaria provando que as duas não se comparam — estaria
    provando que a fixture não distingue o caso. Aqui A é afastado de propósito.
    """
    bruto = carregar_json("massa_a_principal.facts.json")
    bruto["window"]["record_count"] = _conversas_dos_facts() + 37  # A ≠ B == C
    facts = AnalysisFacts.model_validate(bruto)
    assert facts.window.record_count != _conversas_dos_facts()

    # C == B (que é o que importa), e A continua diferente: MONTA.
    v2 = assemble_v2(facts, _analytics()).public_result

    assert v2.summary.engine_window_record_count == _conversas_dos_facts() + 37
    assert v2.analytics.record_count == _conversas_dos_facts()


def test_withheld_NAO_tem_contagem_para_reconciliar() -> None:
    """Ausência não é discordância. Exigir igualdade contra um denominador que não existe faria
    `withheld` virar conflito — e `withheld` é justamente o caso sem projeção."""
    v2 = assemble_v2(
        _facts(),
        _analytics(component_status=ComponentStatus.WITHHELD, data=None, record_count=None),
    )

    assert v2.public_result.analytics.record_count is None


# ── a trava que teria pego meu erro ─────────────────────────────────────────


def test_o_id_publico_da_contagem_e_RESOLVIDO_pelo_registro() -> None:
    """**A trava contra a invariante vazia.**

    A primeira versão deste módulo procurava o indicador pelo id do FATO
    (`observed_conversations`) entre os indicadores PÚBLICOS, cujo id é
    `analyzed_conversation_count`. O laço nunca achava nada, e a invariante B == C passava
    sempre — sem comparar coisa nenhuma.

    Uma trava que nunca dispara é pior que trava nenhuma: ela dá a impressão de que alguém está
    olhando.
    """
    publico = _id_publico_das_conversas()

    assert publico == "analyzed_conversation_count"
    assert publico != "observed_conversations", "o id do fato não é o id público"
    # E ele EXISTE entre os indicadores publicados — senão a invariante não teria lado esquerdo.
    v2 = assemble_v2(_facts(), _analytics()).public_result
    assert publico in [i.id for i in v2.indicators]
