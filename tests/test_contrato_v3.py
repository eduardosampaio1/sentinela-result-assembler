"""R2 — o contrato `analysis-result-v3`: o que ele garante e o que ele recusa.

Cada caso aqui existe por um defeito medido, não por completude de cobertura:

- **absence-as-zero** foi a razão de `consistency_score` e `global_confidence` ficarem fora
  do v1. O envelope os destrava separando valor de disponibilidade — e só destrava de
  verdade se o contrato **recusar** as combinações incoerentes;
- **`dimensions: []`** durou meses porque nada distinguia "sem produtor" de "produziu
  zero". A regra omitido × vazio existe contra isso, e é verificável;
- **escala convertida em silêncio** é o defeito que ainda não aconteceu. `response_stability`
  sai 0..100 do motor; se alguém dividir por 100 na publicação, o consumidor recebe um
  número diferente do que foi medido e não tem como saber.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from result_assembler.contracts.facts import Availability, Reason
from result_assembler.contracts.result import IndicatorState, Partiality, PublicSummary
from result_assembler.contracts.result_v3 import (
    RESULT_V3_SCHEMA_VERSION,
    Domain,
    MethodMetadata,
    PublicIndicatorV3,
    PublicIntent,
    PublicMeasurement,
    PublicProjection,
    PublicResultV3,
    PublicRisk,
    PublicScore,
    Scale,
    ScaleKind,
)

RATIO = Scale(kind=ScaleKind.RATIO_UNIT)
CEM = Scale(kind=ScaleKind.SCORE_100)


def medicao(id_: str = "m", **kw) -> PublicMeasurement:
    base = dict(
        id=id_,
        value=0.5,
        availability=Availability.AVAILABLE,
        reason=Reason.OK,
        scale=RATIO,
    )
    base.update(kw)
    return PublicMeasurement(**base)


def ausente(id_: str = "m", motivo: Reason = Reason.NO_INPUT_DATA) -> PublicMeasurement:
    return PublicMeasurement(
        id=id_,
        value=None,
        availability=Availability.UNAVAILABLE,
        reason=motivo,
        scale=RATIO,
    )


def documento(**kw) -> PublicResultV3:
    base = dict(
        analysis_id="an-1",
        indicator_registry_version="indicator-registry-1.0",
        measurement_contract_version="measurement-1.0",
        argos_catalog_version="argos-catalog-1.0",
        summary=PublicSummary(record_count=100, analyzed_at="2026-08-12T00:00:00Z"),
        method=MethodMetadata(),
        partiality=Partiality(complete=True, reasons=()),
    )
    base.update(kw)
    return PublicResultV3(**base)


# ═══════════════════════════════════════════════════════════════════════════════════════
# 1. O envelope recusa o incoerente
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_medicao_disponivel_com_valor_e_valida() -> None:
    # Anti-vacuidade: sem este caso, os de recusa abaixo passariam num contrato que recusa
    # tudo.
    assert medicao().value == 0.5


def test_zero_REAL_e_medido_e_continua_valido() -> None:
    # A distinção que o contrato inteiro existe para preservar: zero medido é um fato.
    assert medicao(value=0.0).value == 0.0


def test_ausencia_nao_carrega_valor() -> None:
    with pytest.raises(ValidationError, match="que diz que ele não existe"):
        PublicMeasurement(
            id="x", value=0.5, availability=Availability.UNAVAILABLE,
            reason=Reason.NO_INPUT_DATA, scale=RATIO,
        )


def test_disponivel_exige_valor() -> None:
    with pytest.raises(ValidationError, match="sem valor"):
        PublicMeasurement(
            id="x", value=None, availability=Availability.AVAILABLE,
            reason=Reason.OK, scale=RATIO,
        )


def test_ok_e_ausencia_se_contradizem() -> None:
    with pytest.raises(ValidationError, match="se contradizem"):
        PublicMeasurement(
            id="x", value=None, availability=Availability.UNAVAILABLE,
            reason=Reason.OK, scale=RATIO,
        )


def test_motivo_de_falha_ao_lado_de_numero_se_contradiz() -> None:
    with pytest.raises(ValidationError, match="se contradizem"):
        PublicMeasurement(
            id="x", value=0.5, availability=Availability.AVAILABLE,
            reason=Reason.INSUFFICIENT_SAMPLE, scale=RATIO,
        )


def test_parcial_exige_cobertura_declarada_e_menor_que_um() -> None:
    with pytest.raises(ValidationError, match="data_coverage"):
        PublicMeasurement(
            id="x", value=0.5, availability=Availability.PARTIAL,
            reason=Reason.OK, scale=RATIO,
        )
    ok = PublicMeasurement(
        id="x", value=0.5, availability=Availability.PARTIAL,
        reason=Reason.OK, scale=RATIO, data_coverage=0.4,
    )
    assert ok.data_coverage == 0.4


# ═══════════════════════════════════════════════════════════════════════════════════════
# 2. Escala é contrato
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_valor_fora_da_faixa_e_erro_de_montagem() -> None:
    with pytest.raises(ValidationError, match="fora de `ratio_unit`"):
        medicao(value=1.4)


def test_response_stability_publica_0_a_100_sem_conversao() -> None:
    # A decisão do owner: a escala do produtor é preservada. `93.0` num `score_100` é
    # válido; o MESMO 93.0 num `ratio_unit` é erro. É isso que impede a conversão silenciosa
    # — ela deixa de ser possível sem alguém trocar a escala declarada, o que é revisável.
    assert PublicMeasurement(
        id="response_stability", value=93.0, availability=Availability.AVAILABLE,
        reason=Reason.OK, scale=CEM,
    ).value == 93.0
    with pytest.raises(ValidationError):
        medicao(id_="response_stability", value=93.0)  # ratio_unit


def test_escala_aberta_nao_impoe_faixa() -> None:
    # Dinheiro e contagem não têm teto contratado. Impor um recusaria dados legítimos.
    assert PublicMeasurement(
        id="total_estimated_cost", value=1_000_000.0, availability=Availability.AVAILABLE,
        reason=Reason.OK, scale=Scale(kind=ScaleKind.CURRENCY), unit="USD",
    ).value == 1_000_000.0


# ═══════════════════════════════════════════════════════════════════════════════════════
# 3. Omitido × vazio
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_familia_omitida_e_familia_vazia_sao_DIFERENTES() -> None:
    sem_produtor = documento()
    produziu_zero = documento(alerts=())
    assert sem_produtor.alerts is None
    assert produziu_zero.alerts == ()
    assert sem_produtor.alerts != produziu_zero.alerts


def test_a_diferenca_sobrevive_a_serializacao() -> None:
    # Se ela morresse no dump, o consumidor — que lê o JSON, não o objeto — não a veria.
    sem = documento().model_dump(mode="json")
    zero = documento(alerts=()).model_dump(mode="json")
    assert sem["alerts"] is None
    assert zero["alerts"] == []


# ═══════════════════════════════════════════════════════════════════════════════════════
# 4. Identidade
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_id_repetido_numa_familia_e_recusado() -> None:
    with pytest.raises(ValidationError, match="id repetido"):
        documento(scores=(PublicScore(measurement=medicao("a")),
                          PublicScore(measurement=medicao("a"))))


def test_a_mesma_projecao_em_horizontes_diferentes_e_LEGITIMA() -> None:
    # O contrário do caso acima, e a razão de `horizon` ser dado: `@month` e `@year` são a
    # mesma métrica, e recusá-las como duplicata forçaria dois ids sintéticos.
    doc = documento(projections=(
        PublicProjection(id="projected_token_cost", horizon="month",
                         measurement=medicao("projected_token_cost",
                                             scale=Scale(kind=ScaleKind.CURRENCY))),
        PublicProjection(id="projected_token_cost", horizon="year",
                         measurement=medicao("projected_token_cost",
                                             scale=Scale(kind=ScaleKind.CURRENCY))),
    ))
    assert len(doc.projections) == 2


def test_o_mesmo_par_id_horizonte_e_recusado() -> None:
    with pytest.raises(ValidationError, match="par \\(id, horizon\\)"):
        documento(projections=(
            PublicProjection(id="p", horizon="month", measurement=medicao("p")),
            PublicProjection(id="p", horizon="month", measurement=medicao("p")),
        ))


# ═══════════════════════════════════════════════════════════════════════════════════════
# 5. As famílias preservam o que o v1 perdia
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_ai_health_declara_as_dimensoes_que_o_compoem() -> None:
    # Sem `composite_of`, uma agregação sobre as dimensões somaria o agregado junto das
    # partes — e o número resultante pareceria legítimo.
    score = PublicScore(
        measurement=medicao("ai_health_score"),
        composite_of=("semantic", "behavioral", "structural", "economic"),
    )
    assert len(score.composite_of) == 4


def test_intencao_preserva_identidade_e_suporte() -> None:
    # Achatada em `indicators[]`, a intenção viraria um id sintético e o suporte amostral
    # não teria onde morar.
    intent = PublicIntent(
        intent_id="reset_senha", score=medicao("intent_score"),
        support=4, severity="critical", underrepresented=True,
    )
    assert intent.intent_id == "reset_senha"
    assert intent.support == 4


def test_risco_sem_faixa_do_produtor_nao_ganha_faixa() -> None:
    # O consumidor nunca deriva limiar de 0..1: escolher onde termina "moderado" é decisão
    # de produto, e tomá-la na apresentação a esconderia de quem a revisa.
    assert PublicRisk(id="containment_risk", measurement=medicao("containment_risk")).band is None


def test_indicador_v3_publica_o_motivo_que_o_v1_retinha() -> None:
    # `not_measured` sem motivo não diz a quem lê o que fazer. Com
    # `dependency_unavailable`, a tela informa "custo indisponível: moeda não declarada".
    ind = PublicIndicatorV3(
        id="total_estimated_cost", state=IndicatorState.NOT_MEASURED,
        reason=Reason.DEPENDENCY_UNAVAILABLE, value=None, kind="currency",
        scale=Scale(kind=ScaleKind.CURRENCY),
    )
    assert ind.reason is Reason.DEPENDENCY_UNAVAILABLE


def test_procedencia_semantica_sem_expor_implementacao() -> None:
    # `domain` responde "de que domínio veio", sem revelar módulo nem função.
    assert medicao(domain=Domain.BEHAVIORAL).domain is Domain.BEHAVIORAL


# ═══════════════════════════════════════════════════════════════════════════════════════
# 6. O documento
# ═══════════════════════════════════════════════════════════════════════════════════════


def test_a_versao_e_declarada_no_documento() -> None:
    assert documento().result_schema_version == RESULT_V3_SCHEMA_VERSION == "analysis-result-v3"


def test_campo_desconhecido_e_recusado() -> None:
    # A rigidez do v1 (`additionalProperties: false`) é o que fez o defeito aparecer em vez
    # de passar calado. O v3 a mantém.
    with pytest.raises(ValidationError):
        documento(campo_que_ninguem_declarou=1)


def test_o_documento_nao_tem_lugar_para_Analytics() -> None:
    # Os dois motores publicam em contratos próprios. A colisão de nome `dimensions` — no
    # Analytics são distribuições categóricas — deixa de ser risco por morarem em
    # documentos diferentes.
    campos = set(PublicResultV3.model_fields)
    assert not {"snapshot", "distributions", "concentrations", "time_series"} & campos
