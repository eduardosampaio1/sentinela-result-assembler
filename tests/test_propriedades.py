"""Property-based nas fronteiras onde exemplos escolhidos a mão não bastam.

Usado só onde o espaço de entrada é grande e a regra é universal: ordem, duplicidade,
números inválidos, campos extras e determinismo. Para semântica (o que 0.85 significa),
exemplo escolhido continua sendo melhor — propriedade não sabe o que é certo.
"""

from __future__ import annotations

import copy
import math

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from massas import carregar_json, com_indicador
from result_assembler import (
    AnalysisFacts,
    AssemblyError,
    DuplicateIndicator,
    assemble,
    serialize_canonical,
)

RAPIDO = settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


@pytest.fixture
def bruto() -> dict:
    return carregar_json("massa_a_principal.facts.json")


@RAPIDO
@given(permutacao=st.permutations(range(11)))
def test_qualquer_ordem_de_chegada_produz_os_mesmos_bytes(permutacao):
    """Determinismo sob permutação: a ordem publicada vem do registro, não do payload."""
    base = carregar_json("massa_a_principal.facts.json")
    referencia = serialize_canonical(assemble(AnalysisFacts.model_validate(base)).public_result)

    embaralhado = copy.deepcopy(base)
    embaralhado["indicators"] = [base["indicators"][i] for i in permutacao]
    obtido = serialize_canonical(
        assemble(AnalysisFacts.model_validate(embaralhado)).public_result
    )
    assert obtido == referencia


@RAPIDO
@given(indice=st.integers(min_value=0, max_value=10))
def test_duplicar_qualquer_indicador_recusa(indice):
    base = carregar_json("massa_a_principal.facts.json")
    base["indicators"].append(copy.deepcopy(base["indicators"][indice]))
    with pytest.raises(DuplicateIndicator):
        assemble(AnalysisFacts.model_validate(base))


@RAPIDO
@given(
    valor=st.one_of(
        st.floats(allow_nan=True, allow_infinity=True).filter(
            lambda v: not math.isfinite(v)
        ),
        st.booleans(),
        st.text(min_size=1, max_size=8),
        st.lists(st.integers(), min_size=1, max_size=2),
    )
)
def test_valor_nao_numerico_ou_nao_finito_nunca_monta(valor):
    """Nenhuma entrada deste conjunto pode virar resultado público — nem por coerção."""
    base = carregar_json("massa_a_principal.facts.json")
    with pytest.raises((ValidationError, AssemblyError)):
        assemble(AnalysisFacts.model_validate(com_indicador(base, value=valor)))


@RAPIDO
@given(
    nome=st.text(
        alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=12
    )
)
def test_campo_extra_com_qualquer_nome_e_recusado(nome):
    """`extra="forbid"` precisa valer para nome nenhum em especial — inclusive um que
    pareça inofensivo."""
    base = carregar_json("massa_a_principal.facts.json")
    conhecidos = set(base["indicators"][0])
    if nome in conhecidos:
        return
    with pytest.raises(ValidationError):
        AnalysisFacts.model_validate(com_indicador(base, **{nome: 1}))


@RAPIDO
@given(valor=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False))
def test_razao_so_monta_dentro_de_zero_um(valor):
    """Fronteira universal: fora de [0,1] recusa; dentro, monta e sai íntegro."""
    base = carregar_json("massa_a_principal.facts.json")
    payload = com_indicador(base, value=valor)
    if 0.0 <= valor <= 1.0:
        r = assemble(AnalysisFacts.model_validate(payload)).public_result
        assert r.indicators[0].value == valor
    else:
        with pytest.raises(AssemblyError):
            assemble(AnalysisFacts.model_validate(payload))


@RAPIDO
@given(ordens=st.lists(st.integers(min_value=0, max_value=50), min_size=3, max_size=3))
def test_ordem_de_recomendacao_precisa_ser_unica_e_manda_na_publicacao(ordens):
    base = carregar_json("massa_f_recomendacoes_evidencias.facts.json")
    for rec, ordem in zip(base["recommendations"], ordens, strict=False):
        rec["order"] = ordem

    if len(set(ordens)) != len(ordens):
        with pytest.raises(AssemblyError):
            assemble(AnalysisFacts.model_validate(base))
        return

    r = assemble(AnalysisFacts.model_validate(base)).public_result
    esperado = [
        rec["id"] for rec in sorted(base["recommendations"], key=lambda x: x["order"])
    ]
    assert [x.id for x in r.recommendations] == esperado
