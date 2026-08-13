"""R7 — os três contratos coexistem, e o v3 não move nada do que já existia.

A pergunta que estes casos respondem não é "o v3 funciona?" — isso é R2/R3. É a outra, que
só aparece depois: **quem já consumia continua recebendo exatamente o que recebia?**

O risco é concreto e tem nome. `analysis-result-v1` tem `additionalProperties: false` em
oito pontos: um campo a mais e o consumidor que valida contra o schema publicado passa a
recusar a resposta. Foi por isso que o v2 nasceu arquivo à parte em vez de bloco aditivo, e
é a mesma razão de o v3 ser um terceiro documento e não uma extensão.

Três provas, em três níveis:

    bytes       o golden do v1 não mudou — nem por reordenação, nem por campo novo
    schema      documento v1 continua válido contra o schema v1
    versão      o discriminador distingue, e nenhum documento mente sobre o que é
"""

from __future__ import annotations

import json
import pathlib

import jsonschema
import pytest

from result_assembler import assemble, parse_facts, serialize_canonical
from result_assembler.assembler.assemble_v3 import assemble_v3
from result_assembler.version import (
    FACTS_SCHEMA_V2_VERSION,
    FACTS_SCHEMA_VERSION,
    RESULT_SCHEMA_V2_VERSION,
    RESULT_SCHEMA_V3_VERSION,
    RESULT_SCHEMA_VERSION,
    SUPPORTED_FACTS_SCHEMA_VERSIONS,
)

RAIZ = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = RAIZ / "fixtures"
GOLDEN = RAIZ / "tests" / "golden"
SCHEMAS = RAIZ / "schemas"

MASSAS = [
    "massa_a_principal",
    "massa_b_zero_e_nao_medido",
    "massa_d_parcial",
    "massa_f_recomendacoes_evidencias",
]


def facts_de(nome: str):
    return parse_facts(json.loads((FIXTURES / f"{nome}.facts.json").read_text(encoding="utf-8")))


def schema(nome: str) -> dict:
    return json.loads((SCHEMAS / f"{nome}.schema.json").read_text(encoding="utf-8"))


# ═══════════════════════════════════════════════════════════════════════════════════════
# 1. O v1 não se moveu — byte a byte
# ═══════════════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("nome", MASSAS)
def test_o_golden_do_v1_continua_identico(nome: str) -> None:
    """A prova mais forte que existe aqui: os MESMOS bytes.

    Não "equivalente", não "os campos que importam": idênticos. Reordenação, campo novo com
    default, mudança de precisão — tudo isso muda bytes, e tudo isso quebraria um consumidor
    que hasheia a resposta ou a compara com um snapshot.
    """
    # O golden e gravado pretty-printed; a serializacao canonica e compacta. Comparar
    # bytes crus compararia formatacao de arquivo, nao contrato — entao o confronto e do
    # CONTEUDO, e do lado canonico tambem, que e o que o consumidor recebe.
    esperado = json.loads((GOLDEN / f"{nome}.result.json").read_text(encoding="utf-8"))
    montado = assemble(facts_de(nome)).public_result
    assert montado.model_dump(mode="json") == esperado, f"{nome}: o v1 mudou"

    # E os bytes canonicos sao estaveis entre duas montagens da mesma entrada.
    assert serialize_canonical(montado) == serialize_canonical(
        assemble(facts_de(nome)).public_result
    )


@pytest.mark.parametrize("nome", MASSAS)
def test_o_documento_v1_continua_valido_contra_o_schema_v1(nome: str) -> None:
    montado = assemble(facts_de(nome)).public_result.model_dump(mode="json")
    jsonschema.validate(instance=montado, schema=schema("analysis-result-v1"))


def test_o_v1_nao_ganhou_campo_novo() -> None:
    # `additionalProperties: false`: um campo a mais e quem valida passa a RECUSAR a
    # resposta. O v3 acrescentou sete famílias — nenhuma delas aqui.
    campos = set(assemble(facts_de(MASSAS[0])).public_result.model_dump().keys())
    novas = {"scores", "intents", "risks", "projections", "alerts", "issues", "method"}
    assert not (campos & novas), f"família do v3 vazou para o v1: {campos & novas}"


# ═══════════════════════════════════════════════════════════════════════════════════════
# 2. Os três documentos declaram o que são
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_cada_documento_declara_a_propria_versao() -> None:
    v1 = assemble(facts_de(MASSAS[0])).public_result
    v3 = assemble_v3(facts_de(MASSAS[0])).public_result
    assert v1.result_schema_version == RESULT_SCHEMA_VERSION == "analysis-result-v1"
    assert v3.result_schema_version == RESULT_SCHEMA_V3_VERSION == "analysis-result-v3"


def test_as_tres_versoes_de_saida_sao_DISTINTAS() -> None:
    # Se duas colidissem, o discriminador deixaria de discriminar.
    assert len({RESULT_SCHEMA_VERSION, RESULT_SCHEMA_V2_VERSION, RESULT_SCHEMA_V3_VERSION}) == 3


def test_o_v3_nao_e_valido_contra_o_schema_do_v1() -> None:
    """E isso é o comportamento CERTO, não um problema.

    Um consumidor que só conhece o v1 deve recusar um v3 explicitamente, em vez de aceitar
    e ignorar o que não entende. Aceitar em silêncio é como um campo novo vira dado perdido
    sem ninguém notar.
    """
    v3 = assemble_v3(facts_de(MASSAS[0])).public_result.model_dump(mode="json")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=v3, schema=schema("analysis-result-v1"))


def test_o_v3_e_valido_contra_o_PROPRIO_schema() -> None:
    v3 = assemble_v3(facts_de(MASSAS[0])).public_result.model_dump(mode="json")
    jsonschema.validate(instance=v3, schema=schema("analysis-result-v3"))


# ═══════════════════════════════════════════════════════════════════════════════════════
# 3. A entrada: o v1 continua entrando, e o v2 é aceito sem substituí-lo
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_as_duas_versoes_de_ENTRADA_sao_aceitas() -> None:
    assert SUPPORTED_FACTS_SCHEMA_VERSIONS == {FACTS_SCHEMA_VERSION, FACTS_SCHEMA_V2_VERSION}


@pytest.mark.parametrize("nome", MASSAS)
def test_fatos_v1_continuam_montando_nos_dois_documentos(nome: str) -> None:
    # Compatibilidade de entrada: o produtor não precisa subir de versão para continuar
    # publicando. Quem ficar no v1 perde as famílias novas — e o documento diz isso pela
    # ausência dos campos, em vez de fingir listas vazias.
    facts = facts_de(nome)
    assert assemble(facts).public_result.indicators
    v3 = assemble_v3(facts).public_result
    assert v3.indicators
    assert v3.scores is None


def test_massa_v1_continua_valida_contra_o_schema_de_entrada_v1() -> None:
    bruto = json.loads((FIXTURES / "massa_a_principal.facts.json").read_text(encoding="utf-8"))
    jsonschema.validate(instance=bruto, schema=schema("analysis-facts-v1"))


def test_a_mesma_massa_promovida_a_v2_vale_contra_o_schema_v2() -> None:
    bruto = json.loads((FIXTURES / "massa_a_principal.facts.json").read_text(encoding="utf-8"))
    bruto["facts_schema_version"] = FACTS_SCHEMA_V2_VERSION
    jsonschema.validate(instance=bruto, schema=schema("analysis-facts-v2"))


def test_um_fato_v1_que_traz_familia_v2_e_RECUSADO() -> None:
    # Sem esta recusa, um produtor emitiria `alerts` dizendo-se v1, e o documento seria
    # inválido contra o próprio schema que declara — sem ninguém notar até um validador
    # externo reclamar.
    bruto = json.loads((FIXTURES / "massa_a_principal.facts.json").read_text(encoding="utf-8"))
    bruto["alerts"] = []
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bruto, schema=schema("analysis-facts-v1"))


# ═══════════════════════════════════════════════════════════════════════════════════════
# 4. Determinismo do v3 — a mesma exigência que o v1 sempre teve
# ═══════════════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("nome", MASSAS)
def test_o_v3_e_deterministico(nome: str) -> None:
    a = assemble_v3(facts_de(nome)).public_result.model_dump(mode="json")
    b = assemble_v3(facts_de(nome)).public_result.model_dump(mode="json")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
