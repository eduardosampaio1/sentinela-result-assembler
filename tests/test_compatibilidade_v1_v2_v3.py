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
    FACTS_SCHEMA_V3_VERSION,
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
# 3. A entrada: o v1 continua entrando, e nem o v2 nem o v3 o substituem
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_as_TRES_versoes_de_ENTRADA_sao_aceitas() -> None:
    # Igualdade e nao `in`: o conjunto e a afirmacao. Uma versao a mais aceita sem passar
    # por aqui seria exatamente o "melhor esforco" que `validate_facts` existe para impedir.
    from result_assembler import FACTS_SCHEMA_V4_VERSION
    assert SUPPORTED_FACTS_SCHEMA_VERSIONS == {
        FACTS_SCHEMA_VERSION,
        FACTS_SCHEMA_V2_VERSION,
        FACTS_SCHEMA_V3_VERSION,
        FACTS_SCHEMA_V4_VERSION,
    }


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


# ═══════════════════════════════════════════════════════════════════════════════════════
# R7-b — o v1 não cresce quando o REGISTRO cresce
#
# ## O buraco que estes casos fecham
#
# A suíte acima prova que o golden do v1 não mudou — sobre `MASSAS`, que são as massas
# ANTIGAS. Quando o registro ganhou quatro saídas para o v3, elas passaram a sair também no
# v1 (`CANONICAL_ORDER` é global e os três montadores leem a mesma lista), e esta suíte
# seguiu VERDE: nenhuma das massas antigas contém os ids novos, então nada as exercitava.
#
# Era um gate que não podia falhar. Provava que o v1 não muda **sobre massa que não exercita
# a mudança**.
#
# Os casos abaixo usam a massa que contém a ordem canônica INTEIRA, e é isso que os torna
# capazes de reprovar.
# ═══════════════════════════════════════════════════════════════════════════════════════

#: Os quatorze que o v1 publica, congelados. Não é cópia de conveniência: é a AFIRMAÇÃO do
#: contrato, escrita aqui para poder discordar do código. Derivá-la de `CANONICAL_ORDER_V1`
#: faria o teste concordar consigo mesmo — trocar um id nos dois lugares passaria.
#:
#: São os ids PÚBLICOS, e a distinção derruba quem não a conhece: `useful_rate` é o id
#: interno do fato; `useful_outcome_rate` é o que o documento publica. A primeira versão
#: desta tupla usou os internos e acusou oito dos QUATORZE como intrusos.
ORDEM_V1_CONGELADA = (
    "useful_outcome_rate",
    "outcome_field_coverage_rate",
    "conversion_rate",
    "intent_coverage_rate",
    "analyzed_conversation_count",
    "useful_outcome_count",
    "handoff_count",
    "conversion_count",
    "total_estimated_cost",
    "token_cost_total",
    "handoff_cost_total",
    "cost_per_useful_outcome",
    "cost_per_session",
    "mean_response_variance_per_intent",
)

#: A massa que exercita a ordem canônica inteira. Sem ela os casos abaixo não medem nada —
#: e é exatamente a lacuna que deixou o defeito passar.
MASSA_COMPLETA = "massa_d1_todas_as_saidas"


def test_o_v1_publica_QUATORZE_mesmo_sobre_massa_com_todas_as_saidas() -> None:
    """Gate 1 — o v1 não cresce quando o registro cresce.

    Roda o montador v1 sobre a massa que traz TODAS as saídas do registro. Se uma entrada
    nova vazar para o v1, ela aparece aqui — e em nenhum outro lugar da suíte.
    """
    publicado = tuple(i.id for i in assemble(facts_de(MASSA_COMPLETA)).public_result.indicators)

    intrusos = [i for i in publicado if i not in ORDEM_V1_CONGELADA]
    assert not intrusos, (
        f"saídas novas vazaram para o v1: {intrusos}. O v1 é imutável — uma saída acrescentada "
        "ao registro para o v3 não pode aparecer nele."
    )
    assert len(publicado) == len(ORDEM_V1_CONGELADA), (
        f"o v1 publicou {len(publicado)} indicadores; o contrato declara "
        f"{len(ORDEM_V1_CONGELADA)}"
    )


def test_a_ordem_do_v1_e_exatamente_a_congelada_e_na_mesma_sequencia() -> None:
    """Gate 2 — conferido por CONTEÚDO e por SEQUÊNCIA, não por comprimento.

    Comprimento sozinho passaria por uma troca de id, e a ADR-004 amarra determinismo à
    ordem: reordenar muda os bytes tanto quanto acrescentar.
    """
    publicado = tuple(i.id for i in assemble(facts_de(MASSA_COMPLETA)).public_result.indicators)
    assert publicado == ORDEM_V1_CONGELADA, (
        "a ordem publicada pelo v1 divergiu da congelada.\n"
        f"  publicado: {publicado}\n"
        f"  congelado: {ORDEM_V1_CONGELADA}"
    )


def test_o_v2_acompanha_o_v1_e_nao_o_v3() -> None:
    """O v2 importa a ordem do v1, e isso é contrato, não detalhe de implementação.

    O v2 nasceu como o v1 mais as famílias analíticas — não como um lugar onde indicador
    novo estreia. Se ele passar a acompanhar o v3, o consumidor do v2 recebe saída que nunca
    lhe foi prometida.
    """
    from result_assembler.assembler.assemble_v2 import (
        AnalyticsComponent,
        ComponentStatus,
        assemble_v2,
    )

    # O v2 exige o componente analítico, e ele aqui é só o VEÍCULO: o que se afere é a ordem
    # dos indicadores, que o v2 herda do v1 — não o conteúdo analítico. `WITHHELD` é o estado
    # que dispensa a projeção (`data=None`); o digest e a versão de contrato continuam
    # obrigatórios, porque retenção declarada ainda precisa dizer o que reteve.
    analytics = AnalyticsComponent(
        component_status=ComponentStatus.WITHHELD,
        projection_digest="d" * 64,
        snapshot_contract_version="analytics-snapshot-v1",
        data=None,
        record_count=None,
    )
    publicado = tuple(
        i.id for i in assemble_v2(facts_de(MASSA_COMPLETA), analytics).public_result.indicators
    )
    intrusos = [i for i in publicado if i not in ORDEM_V1_CONGELADA]
    assert not intrusos, f"saídas novas vazaram para o v2: {intrusos}"


def test_o_v3_publica_as_dezoito_e_comeca_pelas_quatorze_do_v1() -> None:
    """Gate 3 — o v3 cresce, e cresce NO FIM.

    Derivar a ordem do v3 da do v1 preserva a posição de todo indicador antigo. Se alguém
    "organizar" a lista do v3, o golden dele muda sem que ninguém tenha pedido — e este caso
    é o que acusa.
    """
    publicado = tuple(i.id for i in assemble_v3(facts_de(MASSA_COMPLETA)).public_result.indicators)
    assert publicado[: len(ORDEM_V1_CONGELADA)] == ORDEM_V1_CONGELADA, (
        "o v3 não começa pela ordem do v1: indicador antigo mudou de posição"
    )
    assert len(publicado) == 18, f"o v3 publicou {len(publicado)}; esperado 18"


def test_a_versao_do_registro_distingue_os_conjuntos() -> None:
    """Uma string de versão, um conjunto de saídas.

    Enquanto o v1 publicar 14 saídas e o v3 publicar 18, o mesmo literal descrevendo os dois
    é uma versão que resolve conjuntos diferentes conforme a data — a propriedade que o lock
    do wheel protege com `(versão, sha256)`.

    ## A assimetria é do contrato, não deste teste

    O v1 guarda a versão do registro no manifesto INTERNO (`AssemblyOutcome.internal_manifest`);
    o v3 a publica no RESULTADO, onde o consumidor a lê — e o `AssemblyV3Outcome` sequer expõe
    manifesto. Ler cada uma de onde ela mora é o que torna a comparação honesta; forçar as
    duas pelo mesmo caminho faria o teste falhar por acesso, não por divergência.
    """
    v1 = assemble(facts_de(MASSA_COMPLETA)).internal_manifest.versions.indicator_registry_version
    v3 = assemble_v3(facts_de(MASSA_COMPLETA)).public_result.indicator_registry_version
    assert v1 != v3, (
        f"v1 e v3 publicam conjuntos diferentes de saídas sob a MESMA versão de registro: {v1}"
    )


def test_a_massa_completa_cobre_a_ordem_do_v3_INTEIRA() -> None:
    """O gate que impede o Gate 1 de envelhecer verde.

    Achado da validação adversarial: se alguém acrescentar uma sexta saída ao registro e à
    `CANONICAL_ORDER_V3` mas esquecer de pô-la nesta massa, o Gate 1 continua passando — ele
    só sabe dizer que o v1 não publicou intruso ENTRE OS QUE A MASSA TRAZ.

    Este caso amarra a massa ao registro: crescer a ordem sem crescer a massa reprova aqui, e
    o operador é obrigado a exercitar o que acabou de acrescentar.
    """
    from result_assembler.registry.indicators import CANONICAL_ORDER_V3

    bruto = json.loads((FIXTURES / f"{MASSA_COMPLETA}.facts.json").read_text(encoding="utf-8"))
    na_massa = {i["id"] for i in bruto["indicators"]}
    faltando = [i for i in CANONICAL_ORDER_V3 if i not in na_massa]
    assert not faltando, (
        f"a massa completa não exercita {faltando} — os gates acima passariam sem medir essas "
        "saídas. Acrescente o fato à massa junto com a entrada no registro."
    )


def test_a_massa_completa_e_aritmeticamente_COERENTE() -> None:
    """Massa de referência não pode afirmar relações impossíveis.

    Achado da validação adversarial: a primeira versão desta massa declarava
    `intent_coverage_rate 0,85` sobre 20 intenções — que implica 17 cobertas — e
    `covered_intents 7` no mesmo documento. Valores plausíveis, relações impossíveis.

    Importa porque a validação do assembler checa faixa e integralidade POR INDICADOR, nunca
    coerência ENTRE indicadores: nada recusaria o documento. E uma fixture é lida como "é
    assim que a saída se parece" — incoerente, ela ensina errado.
    """
    bruto = json.loads((FIXTURES / f"{MASSA_COMPLETA}.facts.json").read_text(encoding="utf-8"))
    v = {i["id"]: i["value"] for i in bruto["indicators"]}

    n = v["observed_conversations"]
    assert round(v["useful_rate"] * n) == v["useful_outcomes"], "taxa útil × N ≠ desfechos úteis"
    assert round(v["conversion_rate"] * n) == v["conversion_count"], "taxa conv. × N ≠ conversões"
    assert (
        round(v["intent_coverage_rate"] * v["intents_detected"]) == v["covered_intents"]
    ), "cobertura × detectadas ≠ cobertas"
    assert v["covered_intents"] <= v["intents_detected"], "cobertas > detectadas"
    assert (
        v["observed_token_cost_total"] + v["observed_handoff_cost_total"]
        == v["total_estimated_cost"]
    ), "as parcelas de custo não somam o total"
    assert abs(v["cost_per_useful_outcome"] - v["total_estimated_cost"] / v["useful_outcomes"]) < 1e-6
    assert abs(v["cost_per_session"] - v["total_estimated_cost"] / n) < 1e-6
