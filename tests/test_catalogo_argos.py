"""GATE 0 — o catálogo ARGOS está inteiro, e o registry não diverge dele.

## O defeito que este arquivo existe para impedir

O discovery de 2026-08-12 mediu 8 das 34 métricas documentadas chegando ao contrato
público. As 26 restantes não foram recusadas: elas não estavam na tabela de 14 ids do
producer, e **nada no sistema comparava as duas listas**. Ausência silenciosa não é
decisão de produto — e sem um gate ela é indistinguível de uma.

Os casos abaixo não medem qualidade de métrica. Eles medem se a CONTABILIDADE fecha:
46 catalogados, cada um numa família só, sem alias, sem sumiço.

## Anti-vacuidade

Um catálogo vazio faria todas as comparações passarem. Por isso a cardinalidade é
verificada primeiro, contra as duas parcelas declaradas (34 + 12) — e não contra
`len()` de si mesmo, que é a tautologia que deixaria o gate verde sobre nada.
"""

from __future__ import annotations

from collections import Counter

import pytest

from result_assembler.registry.argos_catalog import (
    ARGOS_CATALOG_VERSION,
    CATALOGO,
    DESCOBERTAS,
    DOCUMENTADAS,
    POR_ID,
    TODAS_AS_FAMILIAS,
    Bloqueio,
    Familia,
    bloqueados,
    da_familia,
    publicaveis,
)
from result_assembler.registry.indicators import (
    INDICATOR_REGISTRY,
    SUPPORTED_DIMENSION_IDS,
)

#: Ids PÚBLICOS que o registry contrata hoje. O registry é indexado por id interno; o que
#: o catálogo conhece é o público, e é por ele que as duas listas se comparam.
_IDS_PUBLICOS_DO_REGISTRY = frozenset(d.public_id for d in INDICATOR_REGISTRY.values())

# ═══════════════════════════════════════════════════════════════════════════════════════
# 1. Anti-vacuidade e cardinalidade
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_o_catalogo_nao_esta_vazio() -> None:
    # Sem isto, todo caso abaixo passaria sobre uma lista vazia.
    assert len(CATALOGO) > 30, "catálogo vazio ou truncado — os demais casos não medem nada"


def test_a_aritmetica_fecha_contra_as_parcelas_declaradas() -> None:
    # 34 originais + 12 extensões catalogadas. Comparar com `len(CATALOGO)`
    # seria comparar a lista consigo mesma.
    assert len(CATALOGO) == DOCUMENTADAS + DESCOBERTAS == 46


def test_publicaveis_mais_bloqueados_reconstroem_o_total() -> None:
    # A partição é exata: nada fica fora das duas metades, nada é contado nas duas.
    assert len(publicaveis()) + len(bloqueados()) == len(CATALOGO)


def test_a_numeracao_e_contigua() -> None:
    # Um buraco na numeração é o sintoma de alguém ter removido uma linha sem decidir.
    assert [o.numero for o in CATALOGO] == list(range(1, len(CATALOGO) + 1))


# ═══════════════════════════════════════════════════════════════════════════════════════
# 2. Identidade — o alias implícito morre aqui
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_nenhum_public_id_repetido() -> None:
    # A primeira versão da spec publicava `Response Variance` como score global E como
    # `mean_response_variance_per_intent` em indicadores. Mesma métrica, duas roupas: a
    # contagem inflava e parecia haver mais publicação do que existia.
    repetidos = [k for k, v in Counter(o.public_id for o in CATALOGO).items() if v > 1]
    assert repetidos == [], f"alias implícito — mesmo output em dois lugares: {repetidos}"


def test_nenhum_nome_de_catalogo_repetido() -> None:
    repetidos = [k for k, v in Counter(o.nome for o in CATALOGO).items() if v > 1]
    assert repetidos == []


def test_cada_output_mora_em_exatamente_uma_familia() -> None:
    familias_por_id: dict[str, set[str]] = {}
    for o in CATALOGO:
        familias_por_id.setdefault(o.public_id, set()).add(o.familia)
    multi = {k: v for k, v in familias_por_id.items() if len(v) > 1}
    assert multi == {}, f"output contado em duas famílias: {multi}"


def test_toda_familia_declarada_e_conhecida() -> None:
    desconhecidas = {o.familia for o in CATALOGO} - TODAS_AS_FAMILIAS
    assert desconhecidas == set()


# ═══════════════════════════════════════════════════════════════════════════════════════
# 3. As famílias que têm forma fechada
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_as_dimensions_sao_exatamente_as_quatro_canonicas() -> None:
    # Os ids públicos são os CURTOS. O motor produz `semantic_health` etc. e a
    # normalização acontece na fronteira de publicação — nunca no motor, que não deve
    # mudar vocabulário por causa de contrato.
    assert sorted(o.public_id for o in da_familia(Familia.DIMENSIONS)) == [
        "behavioral",
        "economic",
        "semantic",
        "structural",
    ]


def test_ai_health_nao_e_a_quinta_dimensao() -> None:
    # Ele é o COMPOSTO das quatro (`build_ai_health_measurement`). Colocá-lo ao lado
    # delas faria qualquer agregação sobre `dimensions[]` somar o agregado junto das
    # partes.
    assert POR_ID["ai_health_score"].familia == Familia.SCORES
    assert "ai_health_score" not in {o.public_id for o in da_familia(Familia.DIMENSIONS)}


def test_os_dois_riscos_e_as_quatro_projecoes() -> None:
    assert len(da_familia(Familia.RISKS)) == 2
    assert len(da_familia(Familia.PROJECTIONS)) == 4


def test_min_samples_e_parametro_e_nao_indicador() -> None:
    # É configuração do método, não algo observado na amostra. Publicá-lo como indicador
    # o faria parecer medida.
    assert POR_ID["min_samples_per_intent"].familia == Familia.METHOD


# ═══════════════════════════════════════════════════════════════════════════════════════
# 4. Bloqueios — ausência DECLARADA
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_exatamente_dois_bloqueados_e_sao_os_de_token_waste() -> None:
    assert sorted(o.public_id for o in bloqueados()) == ["token_waste", "token_waste_cost"]


def test_todo_bloqueado_declara_motivo_e_todo_publicavel_nao() -> None:
    # Bloqueio sem motivo é ausência silenciosa com outro nome.
    for o in bloqueados():
        assert o.bloqueio == Bloqueio.SEMANTICA_DE_MEDIDA, o.public_id
    for o in publicaveis():
        assert o.bloqueio is None, o.public_id


def test_bloqueado_nunca_vira_indicador_publico() -> None:
    # A regra do owner: não mascarar como `not_measured`. `not_measured` diz "tentamos e
    # não deu"; bloqueado é "o produto decidiu não publicar". São coisas diferentes, e o
    # consumidor precisa poder distinguí-las.
    for o in bloqueados():
        assert o.public_id not in _IDS_PUBLICOS_DO_REGISTRY, (
            f"{o.public_id} está bloqueado no catálogo e mesmo assim é contratado pelo "
            "registry — o bloqueio não seria respeitado na montagem"
        )


# ═══════════════════════════════════════════════════════════════════════════════════════
# 5. Catálogo × registry — a divergência que ninguém media
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_o_registry_contrata_indicadores_de_verdade() -> None:
    # Anti-vacuidade do lado do registry: com ele vazio, o cruzamento abaixo passaria.
    assert len(_IDS_PUBLICOS_DO_REGISTRY) >= 14


def test_todo_indicador_do_registry_esta_no_catalogo() -> None:
    # O sentido que descobriu os 5 extras: o contrato publicava indicadores que o
    # documento de produto não descrevia. Agora eles estão catalogados — e um sexto não
    # aparece sem alguém decidir.
    fora = sorted(pid for pid in _IDS_PUBLICOS_DO_REGISTRY if pid not in POR_ID)
    assert fora == [], f"registry publica id ausente do catálogo ARGOS: {fora}"


def test_as_dimensions_do_registry_batem_com_as_do_catalogo() -> None:
    # Duas listas das mesmas quatro dimensões existem hoje (registry e catálogo). Enquanto
    # existirem duas, elas precisam concordar por teste — senão divergem em silêncio.
    assert set(SUPPORTED_DIMENSION_IDS) == {
        o.public_id for o in da_familia(Familia.DIMENSIONS)
    }


@pytest.mark.parametrize("output", [o for o in CATALOGO if o.familia == Familia.INDICATORS])
def test_indicador_catalogado_ou_ja_existe_no_registry_ou_e_expansao_declarada(
    output: object,
) -> None:
    # Nem todo indicador catalogado existe no registry HOJE — as ondas R2/R3 os trazem.
    # O que este caso proíbe é o inverso: um id catalogado que nunca poderá existir
    # porque o nome não é sequer um identificador válido.
    pid = output.public_id  # type: ignore[attr-defined]
    assert pid.replace("_", "").replace("@", "").isalnum(), pid


def test_a_versao_do_catalogo_e_declarada() -> None:
    assert ARGOS_CATALOG_VERSION.startswith("argos-catalog-")
