"""D2 — as quatro famílias quantitativas atravessam, e com escala.

O que estes gates protegem, na ordem em que os defeitos apareceram:

1. **A porta.** `parse_facts` fixava `AnalysisFacts` (v1) e o contrato é `extra="forbid"`:
   um documento v2 ou v3 era RECUSADO. As famílias existiam no contrato e não tinham por
   onde entrar. O gate central é o que prova que um documento v3 vira objeto v3 — porque
   parseá-lo como v1 não é perder campo, é publicar `scores: null` ("ninguém produziu")
   sobre um documento que trazia scores.

2. **As duas visões.** O v1 e o v3 são montados a partir do MESMO objeto, de propósito.
   Travar cada montador na sua versão mataria a rota do v1 no dia do bump.

3. **A escala, aferida no DESTINO.** No `analysis-result-v3` serializado, não no fato. Foi
   o erro que o owner pegou na D1: medir disponibilidade e chamar de escala.
"""

from __future__ import annotations

import copy
import json
import pathlib

import pytest

from result_assembler import assemble, assemble_v3, parse_facts
from result_assembler.contracts.facts import (
    AnalysisFacts,
    AnalysisFactsV2,
    AnalysisFactsV3,
)
from result_assembler.assembler.assemble_v3 import EscalaNaoDeclarada
from result_assembler.errors import AssemblyError, SchemaMismatch
from result_assembler.version import (
    FACTS_SCHEMA_V2_VERSION,
    FACTS_SCHEMA_V3_VERSION,
    FACTS_SCHEMA_VERSION,
)

FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "fixtures"

_PROC = {"calculation_version": "1.0", "source": "engine.business.impact_model"}


def _base() -> dict:
    return json.loads((FIXTURES / "massa_d1_todas_as_saidas.facts.json").read_text(encoding="utf-8"))


def _documento_v3(**familias) -> dict:
    """Documento v3 completo. `familias` sobrescreve o que o teste quiser."""
    doc = copy.deepcopy(_base())
    doc["facts_schema_version"] = FACTS_SCHEMA_V3_VERSION
    doc["scores"] = [
        {
            "id": "ai_health_score",
            "value": 0.7621,
            "availability": "available",
            "reason": "ok",
            "composite_of": ["semantic", "behavioral", "structural", "economic"],
            "calculation_version": "1.0",
            "source": "core._engine_helpers.build_ai_health_measurement",
        }
    ]
    doc["risks"] = [
        {"id": "containment_risk", "value": 0.2, "availability": "available",
         "reason": "ok", "band": "moderate", **_PROC},
        {"id": "conversion_risk", "value": 0.35, "availability": "available",
         "reason": "ok", **_PROC},
    ]
    doc["projections"] = [
        {"id": "projected_handoff_cost", "horizon": "month", "value": 72.0,
         "availability": "available", "reason": "ok", "currency": "USD",
         "basis": "observed_handoff_cost", **_PROC},
        # Sem base observada: o portão monetário do produtor não deixa passar número.
        {"id": "projected_token_cost", "horizon": "month", "value": None,
         "availability": "unavailable", "reason": "dependency_unavailable", **_PROC},
    ]
    doc["intents"] = [
        {"intent_id": "saudacao", "support": 12,
         "score": {"id": "intent_score", "value": 82.0, "availability": "available",
                   "reason": "ok", "calculation_version": "1.0", "source": "engine.governance"},
         "response_variance": {"id": "response_variance", "value": 0.41,
                               "availability": "available", "reason": "ok",
                               "calculation_version": "1.0", "source": "engine.governance"}},
        {"intent_id": "cancelamento", "support": 2, "severity": "high",
         "score": {"id": "intent_score", "value": 31.0, "availability": "available",
                   "reason": "ok", "calculation_version": "1.0", "source": "engine.governance"}},
    ]
    doc["method"] = {"min_samples_per_intent": 5}
    doc.update(familias)
    return doc


def _publicado(doc: dict) -> dict:
    """O JSON público — que é onde o consumidor lê, e portanto onde se afere."""
    return assemble_v3(parse_facts(doc)).public_result.model_dump(mode="json")


# ═══════════════════════════════════════════════════════════════════════════════════════
# 1. A porta: a classe corresponde à versão DECLARADA, nunca mais estreita
# ═══════════════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "versao,classe",
    [
        (FACTS_SCHEMA_VERSION, AnalysisFacts),
        (FACTS_SCHEMA_V2_VERSION, AnalysisFactsV2),
        (FACTS_SCHEMA_V3_VERSION, AnalysisFactsV3),
    ],
)
def test_a_porta_devolve_a_classe_da_versao_declarada(versao: str, classe: type) -> None:
    doc = copy.deepcopy(_base())
    doc["facts_schema_version"] = versao
    assert type(parse_facts(doc)) is classe


def test_documento_v3_nao_vira_objeto_v1_calado() -> None:
    """O gate central da fatia.

    Se a porta voltar a fixar o v1, este teste morre por onde tem que morrer: o documento
    TRAZ scores e o resultado diria `null`. Não é campo perdido — é o assembler afirmando
    "ninguém produziu" sobre algo que foi produzido.
    """
    doc = _documento_v3()
    fatos = parse_facts(doc)
    assert isinstance(fatos, AnalysisFactsV3)

    publicado = assemble_v3(fatos).public_result.model_dump(mode="json")
    assert publicado["scores"] is not None, "documento trazia scores e o resultado diz null"
    assert publicado["scores"][0]["measurement"]["value"] == 0.7621


def test_versao_de_entrada_desconhecida_e_recusada_na_porta() -> None:
    doc = copy.deepcopy(_base())
    doc["facts_schema_version"] = "analysis-facts-v9"
    with pytest.raises(SchemaMismatch):
        parse_facts(doc)


def test_a_versao_declarada_nao_vaza_para_a_mensagem_de_erro() -> None:
    """A versão vem do payload, e payload não entra em log (mesmo motivo do `_local_seguro`)."""
    doc = copy.deepcopy(_base())
    doc["facts_schema_version"] = "Bearer sk-live-nao-deve-aparecer"
    with pytest.raises(SchemaMismatch) as erro:
        parse_facts(doc)
    assert "sk-live" not in str(erro.value)


# ═══════════════════════════════════════════════════════════════════════════════════════
# 2. As duas visões saem do MESMO objeto
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_o_v1_continua_montando_sobre_um_objeto_v3() -> None:
    """O acoplamento é deliberado: uma leitura do artefato alimenta as duas montagens.

    Recusar o objeto v3 no montador do v1 mataria a rota do v1 no dia em que o produtor
    subisse de versão. O v1 ser mais estreito não é perda — é a visão contratada dele.
    """
    fatos = parse_facts(_documento_v3())
    v1 = assemble(fatos).public_result.model_dump(mode="json")
    assert v1["indicators"], "a visao v1 secou ao ver um objeto v3"
    assert "scores" not in v1 and "risks" not in v1


def test_as_duas_visoes_descrevem_a_mesma_analise() -> None:
    fatos = parse_facts(_documento_v3())
    v1 = assemble(fatos).public_result
    v3 = assemble_v3(fatos).public_result
    assert str(v1.analysis_id) == str(v3.analysis_id)


# ═══════════════════════════════════════════════════════════════════════════════════════
# 3. Escala, aferida no DESTINO
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_o_escore_de_saude_declara_a_escala_DO_PRODUTOR() -> None:
    """`measurements.ai_health` vive em 0..1 — medido no motor, nao inferido do nome.

    O legado `business_impact.ai_health_score` e o MESMO numero vezes 100. Declarar
    `score_100` aqui faria 0.76 ser lido como saude pessima; multiplicar por 100 seria a
    normalizacao nao autorizada que o `ScaleKind` proibe em docstring.
    """
    for s in _publicado(_documento_v3())["scores"]:
        assert s["measurement"]["scale"]["kind"] == "ratio_unit"


def test_a_escala_do_escore_e_afirmada_SOZINHA_pelo_teste() -> None:
    """Cadeado PRECISO, e existe por causa de uma mutacao que morreu demais.

    Trocar `score_100` por `ratio_unit` no registro derrubava catorze testes — mas por
    causa do invariante de faixa (76.48 nao cabe em 0..1), nao por causa da asserção de
    escala. Dois guardas, e o de fora mascarando o de dentro: se o invariante de faixa
    sumisse um dia, a escala trocada passaria calada.

    Aqui o valor cabe nas DUAS faixas. Entao so a escala pode reprovar.
    """
    doc = _documento_v3()
    doc["scores"][0]["value"] = 0.5  # valido em ratio_unit E em score_100
    assert _publicado(doc)["scores"][0]["measurement"]["scale"]["kind"] == "ratio_unit"


def test_todo_risco_publicado_declara_ratio_unit() -> None:
    for r in _publicado(_documento_v3())["risks"]:
        assert r["measurement"]["scale"]["kind"] == "ratio_unit"


def test_toda_projecao_publicada_declara_currency() -> None:
    for p in _publicado(_documento_v3())["projections"]:
        assert p["measurement"]["scale"]["kind"] == "currency"


def test_a_intencao_publica_escala_no_escore_e_na_variancia() -> None:
    intencoes = _publicado(_documento_v3())["intents"]
    assert intencoes[0]["score"]["scale"]["kind"] == "score_100"
    # `raw` é a resposta honesta: é a única medida do catálogo em que MAIOR é PIOR, e a
    # faixa é decisão de produto em aberto. Inventar um teto inverteria a leitura da barra.
    assert intencoes[0]["response_variance"]["scale"]["kind"] == "raw"


def test_a_moeda_atravessa_junto_da_projecao_monetaria() -> None:
    """Faixa aberta não dispensa unidade: sem moeda, o número não é dinheiro."""
    mensal = next(
        p for p in _publicado(_documento_v3())["projections"]
        if p["measurement"]["value"] is not None
    )
    assert mensal["currency"] == "USD"


def test_id_sem_escala_declarada_falha_FECHADA() -> None:
    """Publicar medição sem faixa seria pior que recusar: o consumidor desenha a barra."""
    doc = _documento_v3()
    doc["risks"] = [
        {"id": "risco_que_ninguem_declarou", "value": 0.5, "availability": "available",
         "reason": "ok", **_PROC}
    ]
    with pytest.raises(EscalaNaoDeclarada):
        assemble_v3(parse_facts(doc))


# ═══════════════════════════════════════════════════════════════════════════════════════
# 4. Ausência: os três estados não colapsam
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_familia_sem_produtor_e_familia_vazia_sao_estados_DIFERENTES() -> None:
    """`None` é ausência de PRODUTOR; `[]` é produtor que rodou e não achou.

    Se um dia isto colapsar, a tela passa a dizer "procuramos riscos e não achamos" sobre
    uma análise que nunca procurou.
    """
    sem_produtor = _publicado(_documento_v3(risks=None))
    rodou_e_nao_achou = _publicado(_documento_v3(risks=[]))
    assert sem_produtor["risks"] is None
    assert rodou_e_nao_achou["risks"] == []


def test_fato_v1_produz_v3_sem_nenhuma_das_quatro_familias() -> None:
    """O v1 não as declara — nem vazias. Este é o caso de produtor que não subiu."""
    publicado = _publicado(copy.deepcopy(_base()))
    for familia in ("scores", "risks", "projections", "intents"):
        assert publicado[familia] is None


def test_projecao_sem_base_observada_sai_None_e_NUNCA_zero() -> None:
    """O portão monetário atravessa o contrato em vez de morrer nele.

    `0.0` aqui seria "projetamos custo zero" — uma afirmação que ninguém fez.
    """
    token = next(
        p for p in _publicado(_documento_v3())["projections"]
        if p["id"] == "projected_token_cost"
    )
    assert token["measurement"]["value"] is None
    assert token["measurement"]["availability"] == "unavailable"
    assert token["currency"] is None
    assert token["basis"] is None


# ═══════════════════════════════════════════════════════════════════════════════════════
# 5. O bloco de método, e o que ele DERIVA
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_min_samples_per_intent_atravessa_ate_o_method() -> None:
    assert _publicado(_documento_v3())["method"]["min_samples_per_intent"] == 5


def test_underrepresented_e_DERIVADO_do_suporte_contra_o_limiar() -> None:
    por_id = {i["intent_id"]: i for i in _publicado(_documento_v3())["intents"]}
    assert por_id["cancelamento"]["underrepresented"] is True  # support 2 < 5
    assert por_id["saudacao"]["underrepresented"] is False  # support 12 >= 5


def test_sem_limiar_declarado_nao_ha_sub_representacao_a_AFIRMAR() -> None:
    """Sem `min_samples_per_intent` o limiar não existe — e afirmar `True` ou `False` sobre
    uma comparação que não pôde ser feita é inventar juízo."""
    publicado = _publicado(_documento_v3(method=None))
    assert all(i["underrepresented"] is False for i in publicado["intents"])


def test_o_produtor_NAO_pode_mandar_underrepresented_pronto() -> None:
    """Duas verdades para o mesmo fato: `support` e o limiar já são publicados, então o
    consumidor refaz a conta. Receber o booleano criaria uma que ninguém consegue conferir."""
    from result_assembler.contracts.facts import FactIntent

    assert "underrepresented" not in FactIntent.model_fields


def test_a_moeda_do_method_NAO_vem_do_bloco_de_metodo() -> None:
    """Ela já viaja junto do valor desde o dataset. Aceitá-la também aqui daria duas fontes
    para o mesmo fato, e no dia em que discordassem não haveria como saber qual valia."""
    from result_assembler.contracts.facts import FactMethod

    assert "currency" not in FactMethod.model_fields
    assert _publicado(_documento_v3())["method"]["currency"] == "USD"


# ═══════════════════════════════════════════════════════════════════════════════════════
# 6. O guarda de versão dentro do montador do v3
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_assemble_v3_recusa_contrato_de_MEDICAO_nao_suportado() -> None:
    """`assemble` e `assemble_v2` chamavam `validate_facts`; o `assemble_v3` NAO chamava.

    Enquanto havia uma versao de entrada isso era divida de rigor. Com tres, e o unico
    guarda entre um documento de versao desconhecida e uma montagem em melhor esforco.

    A porta nao pega este caso: `measurement_contract_version` e campo livre no modelo, e
    so `validate_facts` confere que ele esta na lista de suportados. Sem esta chamada, o
    v3 montaria sobre um contrato de medicao que ninguem sabe interpretar.
    """
    doc = _documento_v3()
    doc["measurement_contract_version"] = "measurement-9.9"
    fatos = AnalysisFactsV3.model_validate(doc)  # o MODELO aceita: nao e ele quem confere
    with pytest.raises(AssemblyError):
        assemble_v3(fatos)


def test_assemble_v3_recusa_indicador_fora_do_REGISTRO() -> None:
    """A outra metade do mesmo guarda: id que o registro nao conhece nao vira medicao."""
    doc = _documento_v3()
    doc["indicators"] = list(doc["indicators"]) + [
        {
            "id": "indicador_que_ninguem_registrou",
            "kind": "count",
            "availability": "available",
            "reason": "ok",
            "value": 1.0,
            "calculation_version": "1.0",
            "source": "engine.business.unit_economics.compute_unit_economics",
        }
    ]
    fatos = AnalysisFactsV3.model_validate(doc)
    with pytest.raises(AssemblyError):
        assemble_v3(fatos)


def test_TODA_classe_do_contrato_de_entrada_e_exportada() -> None:
    """Cadeado contra uma omissao que ja aconteceu e ninguem viu por uma fatia inteira.

    O `__all__` exportava as classes de fato do v1 (`FactIndicator`, `FactDimension`, ...) e
    NAO as do v2 (`FactAlert`, `FactIssue`, `FactExecutiveSummary`, `AnalysisFactsV2`). Elas
    continuavam importaveis, entao nada quebrava — o que quebrava era a DECLARACAO: a
    superficie publica do pacote nao dizia o que o release tinha introduzido.

    As minhas repetiriam a omissao. Este teste faz o proximo bump reprovar em vez de repetir.
    """
    import result_assembler as ra
    from result_assembler.contracts import facts as modulo

    # `FactsModel` e a BASE estrita (`extra="forbid"`, `frozen`), nao uma familia do
    # documento. Consumidor nenhum a constroi; exporta-la sugeriria que ela e um envelope.
    INTERNAS = {"FactsModel"}

    do_contrato = {
        nome
        for nome in dir(modulo)
        if nome not in INTERNAS
        and (nome.startswith("Fact") or nome.startswith("AnalysisFacts"))
        and isinstance(getattr(modulo, nome), type)
        and getattr(modulo, nome).__module__ == modulo.__name__
    }
    assert do_contrato, "a varredura nao achou classe nenhuma — o teste perdeu a ancora"

    faltando = sorted(do_contrato - set(ra.__all__))
    assert not faltando, f"classes do contrato fora do `__all__`: {faltando}"
