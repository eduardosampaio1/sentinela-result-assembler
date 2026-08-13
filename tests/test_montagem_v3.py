"""R3 — a montagem do v3, sobre fatos REAIS.

As massas destas fixtures não foram escritas à mão: vieram de executar o código analítico
real (`docs/PROVENANCE.md`). Montar sobre elas é o que impede o teste provar uma forma que
o produtor nunca emite.

O que os casos travam, e por quê:

- **`reason` atravessa.** O v1 o retinha em `WITHHELD_INTERNAL_FIELDS`, e "não medido" sem
  motivo não diz a quem lê o que fazer. Com `dependency_unavailable`, a tela informa "custo
  indisponível: moeda não declarada";
- **omitido × vazio nasce na montagem.** Depois de montado o documento não sabe mais qual
  das duas era, então a distinção precisa ser criada aqui;
- **escala não é escolhida pelo montador.** Um `kind` sem escala declarada PARA a montagem,
  em vez de virar `raw` por omissão.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from result_assembler import parse_facts
from result_assembler.assembler.assemble_v3 import (
    EscalaNaoDeclarada,
    _escala_de,
    assemble_v3,
)
from result_assembler.contracts.result_v3 import RESULT_V3_SCHEMA_VERSION, ScaleKind
from result_assembler.registry.argos_catalog import ARGOS_CATALOG_VERSION

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures"


def massa(nome: str):
    return parse_facts(json.loads((FIXTURES / nome).read_text(encoding="utf-8")))


@pytest.fixture()
def principal():
    return assemble_v3(massa("massa_a_principal.facts.json")).public_result


# ═══════════════════════════════════════════════════════════════════════════════════════
# 1. Monta, e monta sobre dado real
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_monta_a_massa_principal(principal) -> None:
    assert principal.result_schema_version == RESULT_V3_SCHEMA_VERSION
    assert principal.argos_catalog_version == ARGOS_CATALOG_VERSION
    assert principal.analysis_id


def test_os_indicadores_chegam_com_valor_medido(principal) -> None:
    # Anti-vacuidade: sem isto, tudo abaixo passaria sobre um documento sem indicadores.
    por_id = {i.id: i for i in principal.indicators}
    assert por_id["useful_outcome_rate"].value == 0.8
    assert por_id["useful_outcome_rate"].state.value == "measured"


def test_a_ordem_e_a_CONTRATADA_e_nao_a_de_chegada(principal) -> None:
    # Se a ordem viesse do payload, o checksum viraria função de quem montou o dict.
    from result_assembler.registry.indicators import CANONICAL_ORDER, definicao_de

    esperada = [
        definicao_de(i).public_id for i in CANONICAL_ORDER if definicao_de(i) is not None
    ]
    obtida = [i.id for i in principal.indicators]
    assert obtida == [pid for pid in esperada if pid in set(obtida)]


# ═══════════════════════════════════════════════════════════════════════════════════════
# 2. O motivo atravessa — o que o v1 retinha
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_todo_indicador_publica_motivo(principal) -> None:
    for ind in principal.indicators:
        assert ind.reason is not None, ind.id


def test_indicador_medido_diz_ok(principal) -> None:
    medidos = [i for i in principal.indicators if i.state.value == "measured"]
    assert medidos
    for ind in medidos:
        assert ind.reason.value == "ok"


def test_o_motivo_da_ausencia_e_ESPECIFICO() -> None:
    # A massa D tem parcialidade declarada; a B tem zero real e não-medido lado a lado.
    # O que se prova aqui é que ausência não colapsa num motivo genérico.
    doc = assemble_v3(massa("massa_b_zero_e_nao_medido.facts.json")).public_result
    ausentes = [i for i in doc.indicators if i.value is None]
    assert ausentes, "a massa B deveria ter indicador não medido"
    for ind in ausentes:
        assert ind.reason.value != "ok"


def test_zero_REAL_continua_medido_e_distinguivel_de_ausencia() -> None:
    # A razão de a massa B existir. Se o montador colapsasse os dois, o consumidor leria
    # "custou zero" onde ninguém mediu.
    doc = assemble_v3(massa("massa_b_zero_e_nao_medido.facts.json")).public_result
    zeros = [i for i in doc.indicators if i.value == 0.0]
    ausentes = [i for i in doc.indicators if i.value is None]
    assert zeros and ausentes
    for z in zeros:
        assert z.state.value == "measured"
    for a in ausentes:
        assert a.state.value != "measured"


# ═══════════════════════════════════════════════════════════════════════════════════════
# 3. Omitido × vazio
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_familia_sem_produtor_sai_AUSENTE_e_nao_vazia(principal) -> None:
    # `analysis-facts-v1` não carrega scores, intents, risks nem projections. O documento
    # montado a partir dele não tem esses campos — e isso é a resposta correta: ninguém os
    # produziu. `[]` diria que produziram e não acharam.
    assert principal.scores is None
    assert principal.intents is None
    assert principal.risks is None
    assert principal.projections is None


def test_dimensoes_ausentes_no_fato_nao_viram_lista_vazia(principal) -> None:
    # A massa A não traz dimensão. Era exatamente `dimensions: []` que durou meses na
    # resposta real parecendo "medimos e não achou".
    assert principal.dimensions is None


def test_a_distincao_sobrevive_ao_JSON(principal) -> None:
    # O consumidor lê o dump, não o objeto.
    d = principal.model_dump(mode="json")
    assert d["scores"] is None
    assert d["indicators"] and isinstance(d["indicators"], list)


# ═══════════════════════════════════════════════════════════════════════════════════════
# 4. Escala: declarada, nunca escolhida pelo montador
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_cada_indicador_declara_escala(principal) -> None:
    for ind in principal.indicators:
        assert ind.scale is not None, ind.id


def test_a_escala_segue_o_kind_do_registro(principal) -> None:
    por_id = {i.id: i for i in principal.indicators}
    assert por_id["useful_outcome_rate"].scale.kind is ScaleKind.RATIO_UNIT
    assert por_id["analyzed_conversation_count"].scale.kind is ScaleKind.COUNT
    assert por_id["total_estimated_cost"].scale.kind is ScaleKind.CURRENCY


def test_kind_sem_escala_declarada_PARA_a_montagem() -> None:
    # Publicar `raw` por omissão faria o montador escolher o que o contrato afirma sobre a
    # faixa de um número — decisão que ele não toma.
    with pytest.raises(EscalaNaoDeclarada):
        _escala_de("kind_que_ninguem_declarou")


# ═══════════════════════════════════════════════════════════════════════════════════════
# 5. Moeda
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_a_moeda_e_promovida_ao_cabecalho(principal) -> None:
    # Ela já viajou junto do valor desde o dataset; aqui só sobe para o consumidor não
    # precisar varrer indicadores para saber em que unidade está o dinheiro.
    assert principal.method.currency == "USD"


def test_o_montador_nao_INVENTA_moeda() -> None:
    # Sem indicador monetário com moeda, o cabeçalho fica vazio. Escolher um default aqui
    # seria a camada de publicação decidindo a unidade do dinheiro.
    from result_assembler.assembler.assemble_v3 import _moeda_declarada

    assert _moeda_declarada(()) is None


# ═══════════════════════════════════════════════════════════════════════════════════════
# 6. Procedência semântica
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_dominio_so_aparece_onde_o_catalogo_o_conhece(principal) -> None:
    # As quatro dimensões SÃO os domínios. Inventar um para `useful_outcome_rate` afirmaria
    # uma classificação que ninguém fez.
    assert all(i.domain is None for i in principal.indicators)


# ═══════════════════════════════════════════════════════════════════════════════════════
# 7. Determinismo
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_a_mesma_entrada_produz_o_mesmo_documento() -> None:
    a = assemble_v3(massa("massa_a_principal.facts.json")).public_result.model_dump(mode="json")
    b = assemble_v3(massa("massa_a_principal.facts.json")).public_result.model_dump(mode="json")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# ═══════════════════════════════════════════════════════════════════════════════════════
# 8. R4 — famílias analíticas, e a distinção que elas obrigam
# ═══════════════════════════════════════════════════════════════════════════════════════


def _v2(**extra):
    """A massa principal promovida a `analysis-facts-v2`, com as famílias pedidas."""
    bruto = json.loads((FIXTURES / "massa_a_principal.facts.json").read_text(encoding="utf-8"))
    bruto["facts_schema_version"] = "analysis-facts-v2"
    bruto.update(extra)
    from result_assembler.contracts.facts import AnalysisFactsV2

    return AnalysisFactsV2.model_validate(bruto)


def test_o_v1_NAO_pode_carregar_familia_que_o_schema_v1_nao_declara() -> None:
    # Sem esta recusa um produtor emitiria `alerts` dizendo-se v1, e o documento seria
    # inválido contra o próprio schema que ele declara — sem ninguém notar até um validador
    # externo reclamar.
    from result_assembler.contracts.facts import AnalysisFactsV2

    bruto = json.loads((FIXTURES / "massa_a_principal.facts.json").read_text(encoding="utf-8"))
    with pytest.raises(Exception, match="analysis-facts-v2"):
        AnalysisFactsV2.model_validate(bruto)  # ainda diz v1


def test_alertas_produzidos_chegam_ao_documento() -> None:
    doc = assemble_v3(_v2(alerts=[{
        "id": "a1", "severity": "high", "code": "cross_intent_reuse",
        "title": "Respostas muito parecidas entre intenções",
        "affected_intents": ["reset_senha", "prazo_entrega"],
    }])).public_result
    assert len(doc.alerts) == 1
    assert doc.alerts[0].code == "cross_intent_reuse"
    assert doc.alerts[0].affected_intents == ("reset_senha", "prazo_entrega")


def test_produtor_que_RODOU_e_nao_achou_publica_lista_vazia() -> None:
    doc = assemble_v3(_v2(alerts=[])).public_result
    assert doc.alerts == ()


def test_produtor_AUSENTE_omite_o_campo() -> None:
    # A distinção inteira, num par de casos. `[]` diz "procuramos e não achamos"; ausente
    # diz "ninguém procurou". Foi `evidence: []` fixo que passou anos dizendo a primeira
    # sobre uma capacidade que era a segunda.
    doc = assemble_v3(_v2()).public_result
    assert doc.alerts is None
    assert doc.issues is None
    assert doc.executive_summary is None


def test_a_distincao_das_familias_analiticas_sobrevive_ao_JSON() -> None:
    vazio = assemble_v3(_v2(alerts=[])).public_result.model_dump(mode="json")
    ausente = assemble_v3(_v2()).public_result.model_dump(mode="json")
    assert vazio["alerts"] == []
    assert ausente["alerts"] is None


def test_o_resumo_executivo_declara_idioma() -> None:
    # Um texto sem idioma declarado não tem como ser apresentado honestamente a quem lê
    # noutro — e o `PublicSummary` do v1 nunca teve onde guardar nem o texto nem o idioma.
    doc = assemble_v3(_v2(executive_summary={
        "language": "pt-BR", "text": "A saúde da IA está em 61,9%.", "generated_by": "engine",
    })).public_result
    assert doc.executive_summary.language == "pt-BR"


def test_fatos_v1_seguem_montando_sem_as_familias(principal) -> None:
    # Compatibilidade: o v1 continua entrando, e o que ele não declara sai ausente.
    assert principal.alerts is None
    assert principal.indicators
