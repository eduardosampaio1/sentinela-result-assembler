"""Todo campo de texto PUBLICADO passa pela varredura — e o schema não vaza nome interno.

## O defeito que este arquivo fecha

A docstring de `validate_evidence_safety` afirmava que o alcance era *"todo texto livre que
atravessa para o documento público"*. O código cobria menos:

* **`alerts[].affected_intents`** é a MESMA string que alimenta o `hint` do motor. O `hint` vira
  `detail` e era varrido; `affected_intents` é publicado ao lado e passava livre. O mesmo texto,
  fail-closed num campo e irrestrito no vizinho.
* **`intents[].intent_id`** é o nome da intenção vindo do dataset do CLIENTE — texto livre quando
  o cliente mapeia uma coluna livre.
* **`intents[].severity_reason`** é frase do motor, publicada, sem rede.

É a lição do alcance maior que a afirmação: a promessa escrita valia mais que o código, e quem
lesse a docstring concluiria que a rede cobria o que não cobria.

## E o vazamento pelo caminho oposto

Docstring de modelo vira `description` no JSON Schema, e os schemas viajam para o front. O nome
da tabela interna da Ingestão e a constraint estavam publicados em quatro schemas — colocados lá
pela justificativa da própria decisão de privacidade. A varredura deste mesmo produto trata
`from orchestrator_\\w+` como padrão proibido.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from result_assembler import assemble_v3
from result_assembler.contracts.facts import AnalysisFactsV3
from result_assembler.errors import UnsafeEvidence

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"

#: Coisas que nunca podem sair, uma por campo recém-coberto.
VAZAMENTOS = "Bearer sk-live-abcdef123"


def _fatos(**familias: object) -> AnalysisFactsV3:
    base = {
        "facts_schema_version": "analysis-facts-v3",
        "measurement_contract_version": "measurement-1.0",
        "identity": {"analysis_id": "an-alcance"},
        "window": {"analyzed_at": "2026-08-23T12:00:00+00:00", "record_count": 10},
        "provenance": {"engine_version": "e1"},
        "indicators": [],
        "dimensions": [],
        "recommendations": [],
        "evidence": [],
    }
    base.update(familias)
    return AnalysisFactsV3.model_validate(base)


def _alerta(**campos: object) -> dict:
    base = {"id": "al-1", "severity": "high", "code": "X", "title": "Titulo"}
    base.update(campos)
    return base


#: `score` e uma MEDIDA, nao um numero solto: ela carrega disponibilidade, versao de calculo e
#: fonte. Um numero cru e recusado pelo contrato — de proposito.
SCORE = {
    "id": "intent_score",
    "availability": "available",
    "value": 0.5,
    "calculation_version": "v1",
    "source": "engine",
}


def _intencao(**campos: object) -> dict:
    base = {"intent_id": "agendamento", "score": dict(SCORE), "support": 10}
    base.update(campos)
    return base


def test_a_massa_atravessa_quando_esta_LIMPA() -> None:
    """Guarda contra o conserto por apagão.

    Sem este caso, uma implementação que recusasse TODA alerta e TODA intenção passaria nos casos
    de recusa abaixo — e mediria uma rede que não deixa nada passar, o que não é uma rede.
    """
    fora = assemble_v3(
        _fatos(
            alerts=[_alerta(affected_intents=["agendamento", "cancelamento"])],
            intents=[_intencao(severity_reason=["score abaixo do piso"])],
        )
    )

    assert fora.public_result.alerts is not None
    assert fora.public_result.alerts[0].affected_intents == ("agendamento", "cancelamento")


def test_affected_intents_e_varrido() -> None:
    """O campo irmão do `detail`, que carregava a mesma string sem rede."""
    with pytest.raises(UnsafeEvidence) as erro:
        assemble_v3(_fatos(alerts=[_alerta(affected_intents=["agendamento", VAZAMENTOS])]))

    assert "affected_intents" in erro.value.location


#: Taxonomia REAL de suporte. Cada uma bateria num padrão escrito para rótulo de máquina.
TAXONOMIA_DO_CLIENTE = [
    pytest.param("senha", id="senha"),
    pytest.param("recuperacao_de_senha", id="recuperacao-de-senha"),
    pytest.param("token_expirado", id="token-expirado"),
    pytest.param("password reset", id="password-reset"),
    pytest.param("select plan", id="select-plan"),
]


@pytest.mark.parametrize("nome", TAXONOMIA_DO_CLIENTE)
def test_a_TAXONOMIA_do_cliente_atravessa(nome: str) -> None:
    """O defeito que este caso fecha, medido em homologação com massa real.

    Uma intenção chamada **`senha`** — recuperação de senha, das mais comuns que existem em
    suporte — batia no padrão `credencial` e derrubava a ANÁLISE INTEIRA:

        MONTAGEM RECUSADA: conteudo proibido (credencial) [em intents[10].intent_id]

    `intent_id` é a **taxonomia do cliente**: ele escolhe os nomes e eles entram pela coluna que
    ele mapeou. Aplicar a régua do rótulo de máquina a ela repete, num campo novo, o defeito que
    a 0.9.1 consertou no trecho.

    O erro nasceu no próprio conserto do alcance da varredura: `intent_id` entrou junto com
    `severity_reason`, que é prosa do MOTOR. Os dois estavam na mesma linha do achado e não
    tinham a mesma origem.
    """
    fora = assemble_v3(_fatos(intents=[_intencao(intent_id=nome)]))

    assert fora.public_result.intents is not None
    assert fora.public_result.intents[0].intent_id == nome


@pytest.mark.parametrize("nome", TAXONOMIA_DO_CLIENTE)
def test_a_taxonomia_do_cliente_atravessa_TAMBEM_em_affected_intents(nome: str) -> None:
    """Mesma origem, mesma régua. `affected_intents` são nomes de intenção do cliente."""
    fora = assemble_v3(_fatos(alerts=[_alerta(affected_intents=[nome])]))

    assert fora.public_result.alerts is not None
    assert fora.public_result.alerts[0].affected_intents == (nome,)


@pytest.mark.parametrize(
    "vazamento",
    [
        pytest.param("worker_id-7", id="identidade-de-execucao"),
        pytest.param("postgres://u:p@db.internal/x", id="dsn"),
        pytest.param("/etc/sentinela/prod.key", id="caminho"),
        pytest.param("s3-bucket-interno", id="chave-de-objeto"),
    ],
)
def test_o_intent_id_com_vazamento_NOSSO_ainda_recusa(vazamento: str) -> None:
    """A contraparte. Sem ela, "consertar" seria remover a varredura do campo.

    **RECUSA e não descarta**, ao contrário do trecho: `intent_id` é CHAVE — ele liga a intenção
    aos alertas e ao rótulo da evidência. Descartar quebraria a integridade referencial do
    documento; publicar um vazamento nosso é inaceitável.
    """
    with pytest.raises(UnsafeEvidence) as erro:
        assemble_v3(_fatos(intents=[_intencao(intent_id=vazamento)]))

    assert "intent_id" in erro.value.location


def test_severity_reason_mantem_a_regua_CHEIA() -> None:
    """Ele é prosa do MOTOR, não do cliente — a distinção que o conserto acima estabelece."""
    with pytest.raises(UnsafeEvidence) as erro:
        assemble_v3(_fatos(intents=[_intencao(severity_reason=["Bearer sk-live-abcdef123"])]))

    assert "severity_reason" in erro.value.location


def test_severity_reason_e_varrido() -> None:
    with pytest.raises(UnsafeEvidence) as erro:
        assemble_v3(
            _fatos(intents=[_intencao(severity_reason=["motivo ok", "/etc/sentinela/prod.key"])])
        )

    assert "severity_reason" in erro.value.location


@pytest.mark.parametrize(
    "proibido",
    [
        pytest.param("orchestrator_ingestion_inbox", id="nome-da-tabela"),
        pytest.param("privacy_clearance = ", id="a-constraint"),
    ],
)
def test_nenhum_schema_publicado_carrega_nome_interno(proibido: str) -> None:
    """Docstring de modelo vira `description`, e o schema viaja para o front.

    O caso lê os arquivos GERADOS, e não o fonte: é o artefato publicado que importa, e ele é o
    que sai do gerador — não o que alguém acha que a docstring diz.
    """
    arquivos = sorted(SCHEMAS.glob("*.schema.json"))
    assert arquivos, f"nenhum schema em {SCHEMAS} — o caso mediria o vazio"

    culpados = [a.name for a in arquivos if proibido in a.read_text(encoding="utf-8")]

    assert not culpados, f"{proibido!r} publicado em {culpados}"


def test_o_teto_do_trecho_atravessa_para_o_schema_publicado() -> None:
    """O contrato de ENTRADA declarava o teto; o que o front lê não declarava nada.

    Quem valida contra o schema publicado, ou dimensiona a tela por ele, não tinha como saber o
    limite.
    """
    for arq, modelo in (
        ("analysis-result-v3", "PublicEvidenceSummaryV3"),
        ("analysis-facts-v3", "FactEvidenceSummary"),
    ):
        s = json.loads((SCHEMAS / f"{arq}.schema.json").read_text(encoding="utf-8"))
        defs = s.get("$defs") or s.get("definitions") or {}
        excerpt = defs[modelo]["properties"]["excerpt"]
        tetos = [v.get("maxLength") for v in excerpt["anyOf"] if v.get("type") == "string"]

        assert tetos == [400], f"{arq}::{modelo} publica excerpt sem teto: {excerpt}"
