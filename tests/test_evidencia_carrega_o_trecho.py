"""O TRECHO observado atravessa até o documento público — e só no v3.

## A decisão

Evidência sem o texto observado não é evidência: o texto é o que mostra ONDE o problema está, e
é o que dá nome à família. Decisão do owner, e a regra anterior — *"não carrega texto livre de
conversa"* — cai com ela.

Ela cai porque a premissa mudou. Quando foi escrita, oito das onze peças de privacidade **não
tinham chamador de produção** (cabeçalho do `gate.py` da Ingestão). Hoje o Privacy Gate é porta
única, cobre sete classes fechadas, e o clearance é garantido por
`check (privacy_clearance = 'passed')` no banco.

## Só no v3, e isso é contrato

`PublicEvidenceSummary` serve v1, v2 e v3, e os dois primeiros têm `additionalProperties: false`
no schema publicado. Campo novo ali é quebra para quem valida contra o contrato que já saiu.
"""

from __future__ import annotations

import pytest

from result_assembler import assemble_v3
from result_assembler.contracts.facts import MAX_EXCERPT_LEN, AnalysisFactsV3
from result_assembler.errors import UnsafeEvidence

TRECHO = "Vou verificar isso para voce e retorno em instantes."


def _fatos(evidencia: dict) -> AnalysisFactsV3:
    return AnalysisFactsV3.model_validate(
        {
            "facts_schema_version": "analysis-facts-v3",
            "measurement_contract_version": "measurement-1.0",
            "identity": {"analysis_id": "an-trecho"},
            "window": {"analyzed_at": "2026-08-23T12:00:00+00:00", "record_count": 10},
            "provenance": {"engine_version": "e1"},
            "indicators": [],
            "dimensions": [],
            "recommendations": [],
            "evidence": [evidencia],
        }
    )


EVIDENCIA = {
    "id": "cross_intent_group-1",
    "kind": "cross_intent_group",
    "observed_count": 34,
    "label": "agendamento,cancelamento",
    "excerpt": TRECHO,
}


def test_o_trecho_chega_ao_documento_publico() -> None:
    fora = assemble_v3(_fatos(EVIDENCIA))
    assert fora.public_result.evidence is not None
    ev = fora.public_result.evidence[0]
    assert ev.excerpt == TRECHO
    # E o que já valia continua: a contagem é o número que sustenta a evidência.
    assert ev.observed_count == 34
    assert ev.label == "agendamento,cancelamento"


def test_evidencia_SEM_trecho_continua_valendo() -> None:
    """Nem toda evidência é texto, e ausência aqui não é falha.

    Sem este caso, uma implementação que exigisse `excerpt` passaria no primeiro e quebraria
    toda evidência não textual — que é a maioria.
    """
    sem = {k: v for k, v in EVIDENCIA.items() if k != "excerpt"}
    fora = assemble_v3(_fatos(sem))
    assert fora.public_result.evidence[0].excerpt is None


def test_trecho_LONGO_e_recusado() -> None:
    """Um excerto é um excerto.

    Publicar a conversa inteira seria republicar o dataset pelo documento de resultado — que é
    outra coisa, e tem outra porta (o export, com retenção e auditoria próprias).
    """
    with pytest.raises(Exception) as erro:
        assemble_v3(_fatos({**EVIDENCIA, "excerpt": "x" * (MAX_EXCERPT_LEN + 1)}))
    # Pode ser recusa do contrato (`max_length`) ou da varredura — as duas são a resposta certa,
    # e o caso não escolhe qual, porque a garantia é "não passa", não "por qual porta".
    assert erro.value is not None


def test_trecho_com_CREDENCIAL_e_recusado() -> None:
    """O Gate cobre o dado do CLIENTE; a varredura cobre o que o NOSSO lado colaria aqui.

    As duas camadas olham para lados diferentes, e por isso nenhuma substitui a outra.
    """
    with pytest.raises(UnsafeEvidence):
        assemble_v3(_fatos({**EVIDENCIA, "excerpt": "Authorization: Bearer sk-live-x"}))


def test_o_v2_NAO_ganhou_o_campo() -> None:
    """O contrato publicado do v2 não se mexe.

    `additionalProperties: false` faz de qualquer acréscimo uma quebra para quem valida. Este
    caso é o que impede alguém de "simplificar" juntando os dois modelos de novo.
    """
    from result_assembler.contracts.result import PublicEvidenceSummary

    assert "excerpt" not in PublicEvidenceSummary.model_fields
