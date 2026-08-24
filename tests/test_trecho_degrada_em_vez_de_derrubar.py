"""O trecho suspeito é DESCARTADO; o documento sai. Os campos NOSSOS continuam recusando.

## O defeito que este arquivo fecha

A varredura de conteúdo nasceu para `label` — prosa **do motor**, num campo de 120 caracteres.
Quando o trecho passou a carregar prosa **do cliente**, ela passou a ser aplicada a conversa real
sem que ninguém casasse as duas coisas. Medido, não suposto — três respostas de suporte
perfeitamente normais derrubavam a análise inteira:

    "Voce pode alterar a senha no aplicativo"       -> `credencial`, pela PALAVRA "senha"
    "Para redefinir sua senha, acesse https://..."  -> `url`, pelo link de ajuda da empresa
    "Please select your plan from the list below"   -> `sql/tabela`, por "select ... from"

`UnsafeEvidence` vira `MontagemRecusada` e a análise sai **sem resultado nenhum** — nem v3, nem
v1. E o v1 caía junto sem sequer publicar o trecho.

## A assimetria que este arquivo trava

Recusar é a resposta certa para `id`, `kind` e `label`: são **nossos**, e um id com
`Bearer sk-live-...` é defeito nosso. Para o trecho é a resposta errada: o conteúdo é, por
decisão do owner, do **cliente**.

Descartar é estritamente melhor nas duas pontas — nunca publica o conteúdo suspeito (mesma
garantia da recusa) e não derruba o resultado (o que a recusa fazia).

## Por que os dois lados precisam de caso

Um arquivo que só provasse "conversa banal passa" seria satisfeito por remover a varredura
inteira. Os casos de vazamento NOSSO são o que impede esse conserto.
"""

from __future__ import annotations

import pytest

from result_assembler import assemble_v3
from result_assembler.contracts.facts import AnalysisFactsV3
from result_assembler.errors import UnsafeEvidence

#: Prosa de suporte real. Cada uma casava com um padrão escrito para rótulo de máquina.
CONVERSA_BANAL = [
    pytest.param("Voce pode alterar a senha no aplicativo", id="palavra-senha"),
    pytest.param(
        "Para redefinir sua senha, acesse https://ajuda.acme.com/conta", id="url-de-ajuda"
    ),
    pytest.param("Please select your plan from the list below", id="select-from-em-ingles"),
    pytest.param("Seu token de acesso expirou, faca login de novo", id="palavra-token"),
    pytest.param("Confirmei o horario e enviei o comprovante", id="sem-padrao-nenhum"),
]

#: Vazamento do NOSSO lado. Nenhum destes é prosa de suporte legítima.
VAZAMENTO_NOSSO = [
    pytest.param("Traceback (most recent call last): File x", id="stack-trace"),
    pytest.param("-----BEGIN RSA PRIVATE KEY-----", id="chave-privada"),
    pytest.param("processado pelo worker_id 7 do lote", id="identidade-de-execucao"),
    pytest.param("baixado do bucket de origem", id="chave-de-objeto"),
    pytest.param("linha lida com select id from orchestrator_jobs", id="tabela-nossa"),
    pytest.param("gravado em /var/lib/sentinela/spool", id="caminho-absoluto"),
]


def _fatos(evidencia: dict) -> AnalysisFactsV3:
    return AnalysisFactsV3.model_validate(
        {
            "facts_schema_version": "analysis-facts-v3",
            "measurement_contract_version": "measurement-1.0",
            "identity": {"analysis_id": "an-degrada"},
            "window": {"analyzed_at": "2026-08-23T12:00:00+00:00", "record_count": 10},
            "provenance": {"engine_version": "e1"},
            "indicators": [],
            "dimensions": [],
            "recommendations": [],
            "evidence": [evidencia],
        }
    )


def _evidencia(**campos: object) -> dict:
    base = {
        "id": "cross_intent_group-agendamento-cancelamento",
        "kind": "cross_intent_group",
        "observed_count": 34,
        "label": "agendamento,cancelamento",
        "excerpt": None,
    }
    base.update(campos)
    return base


@pytest.mark.parametrize("texto", CONVERSA_BANAL)
def test_conversa_banal_atravessa_inteira(texto: str) -> None:
    """O caso que estava quebrado: conversa normal publica o trecho, sem perder nada."""
    fora = assemble_v3(_fatos(_evidencia(excerpt=texto)))

    assert fora.public_result.evidence is not None
    assert fora.public_result.evidence[0].excerpt == texto


@pytest.mark.parametrize("texto", VAZAMENTO_NOSSO)
def test_vazamento_nosso_perde_o_trecho_mas_o_documento_sai(texto: str) -> None:
    """As duas metades importam: o trecho NÃO sai, e o resto SAI.

    Um caso que só conferisse `excerpt is None` passaria com a montagem recusada — não haveria
    documento para olhar. A asserção de que o documento existe é o que separa "descartou" de
    "derrubou".
    """
    fora = assemble_v3(_fatos(_evidencia(excerpt=texto)))

    assert fora.public_result.evidence is not None, "o documento tem que sair"
    ev = fora.public_result.evidence[0]
    assert ev.excerpt is None, "o conteudo suspeito nao pode ser publicado"
    # O resto da evidência sobrevive: perder o trecho não é perder a evidência.
    assert ev.observed_count == 34
    assert ev.label == "agendamento,cancelamento"


@pytest.mark.parametrize(
    "campo,valor",
    [
        pytest.param("id", "Bearer sk-live-abcdef", id="id-com-credencial"),
        pytest.param("label", "/etc/sentinela/secrets/prod", id="label-com-caminho"),
        pytest.param("kind", "job_id-7", id="kind-com-identidade"),
        pytest.param("label", "x" * 121, id="label-acima-do-teto"),
    ],
)
def test_a_porta_nossa_continua_recusando(campo: str, valor: str) -> None:
    """A degradação vale só para o trecho. Nos NOSSOS campos, recusar continua sendo certo."""
    with pytest.raises(UnsafeEvidence) as erro:
        assemble_v3(_fatos(_evidencia(**{campo: valor})))

    assert campo in erro.value.location


def test_o_v1_nao_cai_por_um_campo_que_ele_nem_publica() -> None:
    """A assimetria que confirmava o defeito.

    `assemble()` compartilha a varredura, e `PublicEvidenceSummary` **não** publica o trecho — de
    propósito. Antes do conserto, um campo que o documento v1 não carrega derrubava o documento v1.
    """
    from result_assembler import assemble
    from result_assembler.contracts.facts import AnalysisFacts

    fatos = AnalysisFacts.model_validate(
        {
            "facts_schema_version": "analysis-facts-v1",
            "measurement_contract_version": "measurement-1.0",
            "identity": {"analysis_id": "an-v1"},
            "window": {"analyzed_at": "2026-08-23T12:00:00+00:00", "record_count": 10},
            "provenance": {"engine_version": "e1"},
            "indicators": [],
            "recommendations": [],
            "evidence": [_evidencia(excerpt="Voce pode alterar a senha no aplicativo")],
        }
    )

    fora = assemble(fatos)

    assert fora.public_result.evidence is not None
    # O v1 nunca teve o campo; o que se prova aqui é que ele não derruba mais por causa dele.
    assert not hasattr(fora.public_result.evidence[0], "excerpt")
