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
    # A contraparte dos casos de DSN acima: link SEM credencial continua sendo prosa de suporte,
    # e barra-lo era o defeito original. Os dois lados precisam de caso, ou "consertar" vira
    # barrar tudo de novo.
    pytest.param("Acesse www.exemplo.com/ajuda ou ligue para o SAC", id="site-sem-esquema"),
    pytest.param("O boleto vence dia 10 e o codigo e 34191790010104351004", id="numero-longo"),
]

#: Vazamento do NOSSO lado. Nenhum destes é prosa de suporte legítima.
VAZAMENTO_NOSSO = [
    pytest.param("Traceback (most recent call last): File x", id="stack-trace"),
    pytest.param("-----BEGIN RSA PRIVATE KEY-----", id="chave-privada"),
    pytest.param("processado pelo worker_id 7 do lote", id="identidade-de-execucao"),
    pytest.param("baixado do bucket de origem", id="chave-de-objeto"),
    pytest.param("linha lida com select id from orchestrator_jobs", id="tabela-nossa"),
    pytest.param("gravado em /var/lib/sentinela/spool", id="caminho-absoluto"),
    # Achados da revisao independente: ao tirar `url` do trecho eu tirei junto a deteccao de
    # STRING DE CONEXAO, que era o unico padrao que a pegava. Um corte largo demais.
    pytest.param(
        "DATABASE_URL=postgres://analytics:supersecret@db.internal/prod", id="dsn-em-env"
    ),
    pytest.param("postgres://user:senha123@db.internal:5432/sentinela", id="dsn-postgres"),
    pytest.param("redis://:token@redis-homol.railway.internal:6379", id="dsn-redis"),
    pytest.param("amqp://guest:guest@broker/vhost", id="dsn-amqp"),
    pytest.param("https://user:pass@interno.exemplo/painel", id="url-com-credencial"),
    pytest.param("API_TOKEN=abc123def456", id="variavel-de-ambiente"),
]


class _StrHostil(str):
    """Uma `str` que explode ao ser inspecionada. Existe so para o caso de robustez."""

    def strip(self) -> str:  # noqa: D102
        raise RuntimeError("hostil")


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


@pytest.mark.parametrize(
    "entrada",
    [
        pytest.param(None, id="None"),
        pytest.param("", id="vazio"),
        pytest.param("   ", id="so-espaco"),
        pytest.param(b"bytes", id="bytes"),
        pytest.param(123, id="int"),
        pytest.param(["lista"], id="lista"),
        pytest.param({"d": 1}, id="dict"),
        pytest.param(object(), id="objeto"),
        # Achado da revisao independente: a guarda de tipo separava nao-`str`, e uma SUBCLASSE
        # hostil de `str` passava por ela e levantava dentro do `re`. A promessa e absoluta.
        pytest.param(_StrHostil("x"), id="subclasse-hostil-de-str"),
    ],
)
def test_trecho_publicavel_NUNCA_levanta(entrada: object) -> None:
    """A docstring dela promete "nunca levanta", e a promessa precisa de caso.

    Sem as guardas, `bytes`, `int` e `list` levantavam `TypeError` dentro do `re` — a promessa
    escrita era mais forte que o código. Inalcançável pelo caminho contratado
    (`FactEvidenceSummary.excerpt` é `str | None`, validado pelo pydantic antes), mas a função é
    exportada, e quem a chama de fora não tem essa garantia.

    Vazio também vira `None`: publicar `""` faz a tela desenhar uma citação em branco, que afirma
    "o trecho é este" apontando para nada.
    """
    from result_assembler.validation.safety import trecho_publicavel

    assert trecho_publicavel(entrada, "evidence[0].excerpt") is None


def test_trecho_publicavel_devolve_o_texto_quando_ele_PODE_sair() -> None:
    """A guarda do caso acima: uma implementação que devolvesse `None` sempre passaria nele."""
    from result_assembler.validation.safety import trecho_publicavel

    texto = "Confirmei o horario e enviei o comprovante"

    assert trecho_publicavel(texto, "evidence[0].excerpt") == texto
