"""Montagem do `analysis-result-v3` — ARGOS completo, e só ARGOS.

## O que este módulo NÃO faz

Não calcula. Não converte escala. Não preenche ausência. Não infere faixa de risco. Não
escolhe moeda. Ele lê fatos declarados e os arruma na forma pública — a mesma disciplina do
`assemble.py` do v1, aplicada a mais famílias.

A tentação nova é a conversão de escala: `response_stability` chega 0..100 e há um
`ratio_unit` logo ao lado. Dividir por 100 aqui seria normalização numérica não autorizada
— e o contrato recusa, porque a escala é declarada no fato e verificada na construção.

## Omitido × vazio, na montagem

Uma família só vira `()` se o produtor a exercitou. Se o fato não a traz, ela sai **ausente**
do documento. É a diferença entre "procurou alertas e não achou" e "ninguém procurou", e ela
precisa nascer aqui: depois de montado, o documento não sabe mais qual das duas era.

`analysis-facts-v1` não carrega scores, intents, risks nem projections. Montar v3 a partir
dele produz um documento sem esses campos — correto, e não vazio.
"""

from __future__ import annotations

from dataclasses import dataclass

from result_assembler.contracts.facts import (
    AnalysisFacts,
    AnalysisFactsV2,
    Availability,
    FactDimension,
    FactIndicator,
)
from result_assembler.contracts.result import (
    IndicatorState,
    Partiality,
    PublicDenominator,
    PublicEvidenceSummary,
    PublicRecommendation,
    PublicSummary,
)
from result_assembler.contracts.result_v3 import (
    RESULT_V3_SCHEMA_VERSION,
    Domain,
    PublicAlert,
    PublicExecutiveSummary,
    PublicIssue,
    MethodMetadata,
    PublicIndicatorV3,
    PublicMeasurement,
    PublicResultV3,
    Scale,
    ScaleKind,
)
from result_assembler.errors import UnknownIndicator
from result_assembler.registry.argos_catalog import ARGOS_CATALOG_VERSION, POR_ID, Familia
from result_assembler.registry.indicators import (
    INDICATOR_REGISTRY_VERSION_V3,
    CANONICAL_ORDER_V3,
    definicao_de,
)

#: Disponibilidade do fato → estado público do indicador. Igual ao v1, de propósito: o
#: vocabulário público não muda por causa de uma versão nova de documento.
_ESTADO_PUBLICO: dict[Availability, IndicatorState] = {
    Availability.AVAILABLE: IndicatorState.MEASURED,
    Availability.PARTIAL: IndicatorState.PARTIALLY_MEASURED,
    Availability.UNAVAILABLE: IndicatorState.NOT_MEASURED,
    Availability.NOT_EVALUABLE: IndicatorState.NOT_APPLICABLE,
    Availability.FAILED: IndicatorState.CALCULATION_FAILED,
}

_MOTIVO_POR_ESTADO: dict[IndicatorState, str] = {
    IndicatorState.PARTIALLY_MEASURED: "indicator_partially_measured",
    IndicatorState.NOT_MEASURED: "indicator_not_measured",
    IndicatorState.NOT_APPLICABLE: "indicator_not_applicable",
    IndicatorState.CALCULATION_FAILED: "indicator_calculation_failed",
}

#: `kind` do registro → escala pública. Mapa FECHADO: um kind novo sem escala declarada
#: para a montagem em vez de escolher `raw` por omissão, que seria o assembler decidindo o
#: que o contrato deve dizer sobre um número.
_ESCALA_POR_KIND: dict[str, ScaleKind] = {
    "ratio": ScaleKind.RATIO_UNIT,
    "count": ScaleKind.COUNT,
    "currency": ScaleKind.CURRENCY,
    "scalar": ScaleKind.RAW,
}

#: As quatro dimensões de saúde são `ratio_unit` por contrato do composto (F2.5).
_ESCALA_DIMENSAO = Scale(kind=ScaleKind.RATIO_UNIT)


class EscalaNaoDeclarada(ValueError):
    """Um `kind` chegou sem escala pública correspondente.

    Recusar é a decisão certa: publicar `raw` por omissão faria o assembler escolher o que
    o contrato afirma sobre a faixa de um número, que é exatamente o tipo de decisão que
    ele não toma.
    """


@dataclass(frozen=True)
class AssemblyV3Outcome:
    public_result: PublicResultV3


def _escala_de(kind: str) -> Scale:
    escala = _ESCALA_POR_KIND.get(kind)
    if escala is None:
        raise EscalaNaoDeclarada(f"`{kind}` não tem escala pública declarada")
    return Scale(kind=escala)


def _dominio_de(public_id: str) -> Domain | None:
    """A procedência semântica, quando o catálogo a conhece.

    Só as quatro dimensões de saúde a declaram hoje — elas SÃO os domínios. Para o resto o
    campo sai `None`, que é honesto: inventar um domínio para `useful_outcome_rate` seria
    afirmar uma classificação que ninguém fez.
    """
    entrada = POR_ID.get(public_id)
    if entrada is None or entrada.familia is not Familia.DIMENSIONS:
        return None
    return Domain(entrada.public_id)


def _publicar_indicador(ind: FactIndicator) -> PublicIndicatorV3:
    defin = definicao_de(ind.id)
    if defin is None:  # pragma: no cover - `validate_facts` já recusou antes
        raise UnknownIndicator("indicador não registrado")

    estado = _ESTADO_PUBLICO[ind.availability]
    denom = (
        PublicDenominator(kind=ind.denominator.kind, value=ind.denominator.value)
        if ind.denominator is not None
        else None
    )
    return PublicIndicatorV3(
        id=defin.public_id,
        state=estado,
        # O v1 retinha o motivo. Publicá-lo é o que transforma "não medido" — que não diz a
        # quem lê o que fazer — em "custo indisponível: moeda não declarada".
        reason=ind.reason,
        value=ind.value,
        kind=defin.kind.value,
        unit=defin.unit,
        currency=ind.currency,
        denominator=denom,
        coverage=ind.data_coverage if estado is IndicatorState.PARTIALLY_MEASURED else None,
        display_precision=defin.display_precision,
        scale=_escala_de(defin.kind.value),
        domain=_dominio_de(defin.public_id),
    )


def _publicar_dimensao(dim: FactDimension) -> PublicMeasurement:
    """A dimensão vira `PublicMeasurement`, não um tipo próprio.

    Ela É uma medição de saúde: valor, disponibilidade, motivo e cobertura. Ter um tipo
    separado, como no v1, obrigava a duplicar os invariantes — e foi por não tê-los que o
    v1 pôde publicar dimensão sem motivo.
    """
    return PublicMeasurement(
        id=dim.id,
        value=dim.value,
        availability=dim.availability,
        reason=dim.reason,
        data_coverage=dim.data_coverage,
        scale=_ESCALA_DIMENSAO,
        domain=_dominio_de(dim.id),
    )


def _ordem_canonica(facts: AnalysisFacts) -> tuple[FactIndicator, ...]:
    """Ordem CONTRATADA, não a de chegada — senão o checksum vira função de quem montou."""
    por_id = {ind.id: ind for ind in facts.indicators}
    # A ordem do v3 DERIVA da do v1: os catorze primeiro, na mesma sequencia, e o
    # que estreou no v3 depois. Indicador antigo nunca muda de posicao.
    return tuple(por_id[i] for i in CANONICAL_ORDER_V3 if i in por_id)


def _partialidade(indicadores: tuple[PublicIndicatorV3, ...]) -> Partiality:
    motivos = {_MOTIVO_POR_ESTADO[i.state] for i in indicadores if i.state in _MOTIVO_POR_ESTADO}
    return Partiality(complete=not motivos, reasons=tuple(sorted(motivos)))


def _moeda_declarada(indicadores: tuple[PublicIndicatorV3, ...]) -> str | None:
    """A moeda da análise, LIDA dos fatos monetários. Não é escolha do assembler.

    Ela já viajou junto do valor desde o dataset; aqui só é promovida ao cabeçalho para o
    consumidor não precisar varrer indicadores para descobrir em que unidade está o
    dinheiro. Divergência entre indicadores seria contradição no fato — e o produtor já a
    recusa antes, porque a unidade é declarada uma vez por dataset.
    """
    moedas = {i.currency for i in indicadores if i.currency}
    return next(iter(moedas)) if len(moedas) == 1 else None


def _publicar_familias_analiticas(facts: AnalysisFacts) -> dict[str, object]:
    """As familias que so o `analysis-facts-v2` carrega.

    Fatos v1 nao as declaram — nem vazias. Devolver `{}` faz os campos sairem AUSENTES do
    documento, que e o que "ninguem produziu" quer dizer. Se um dia alguem trocar isto por
    `()`, o consumidor passa a ler "procuramos alertas e nao achamos" sobre uma analise que
    nunca procurou.
    """
    if not isinstance(facts, AnalysisFactsV2):
        return {}

    saida: dict[str, object] = {}
    if facts.alerts is not None:
        saida["alerts"] = tuple(
            PublicAlert(
                id=a.id, severity=a.severity, code=a.code, title=a.title,
                detail=a.detail, evidence_refs=a.evidence_refs,
                affected_intents=a.affected_intents,
            )
            for a in facts.alerts
        )
    if facts.issues is not None:
        saida["issues"] = tuple(
            PublicIssue(
                id=i.id, severity=i.severity, code=i.code, title=i.title,
                evidence_refs=i.evidence_refs,
            )
            for i in facts.issues
        )
    if facts.executive_summary is not None:
        resumo = facts.executive_summary
        saida["executive_summary"] = PublicExecutiveSummary(
            language=resumo.language, text=resumo.text, generated_by=resumo.generated_by
        )
    return saida


def assemble_v3(facts: AnalysisFacts) -> AssemblyV3Outcome:
    """`analysis-facts-*` → `analysis-result-v3`.

    Famílias que o fato não traz saem AUSENTES do documento, não vazias. Montar a partir de
    `analysis-facts-v1` — que não carrega scores, intents, risks nem projections — produz um
    v3 sem esses campos, e isso é a resposta correta: ninguém os produziu.
    """
    indicadores = tuple(_publicar_indicador(i) for i in _ordem_canonica(facts))
    dimensoes = tuple(_publicar_dimensao(d) for d in facts.dimensions)

    recomendacoes = tuple(
        PublicRecommendation(
            id=r.id,
            title=r.title,
            priority=r.priority,
            category=r.category,
            evidence_refs=r.evidence_refs,
        )
        for r in sorted(facts.recommendations, key=lambda r: r.order)
    )
    evidencias = tuple(
        PublicEvidenceSummary(id=e.id, kind=e.kind, observed_count=e.observed_count, label=e.label)
        for e in facts.evidence
    )

    publico = PublicResultV3(
        analysis_id=facts.identity.analysis_id,
        result_schema_version=RESULT_V3_SCHEMA_VERSION,
        indicator_registry_version=INDICATOR_REGISTRY_VERSION_V3,
        measurement_contract_version=facts.measurement_contract_version,
        argos_catalog_version=ARGOS_CATALOG_VERSION,
        summary=PublicSummary(
            record_count=facts.window.record_count,
            analyzed_at=facts.window.analyzed_at,
        ),
        method=MethodMetadata(currency=_moeda_declarada(indicadores)),
        partiality=_partialidade(indicadores),
        indicators=indicadores,
        # `or None`: um fato sem dimensão nenhuma não exercitou a capacidade, e `()` diria
        # que exercitou e não achou. A distinção morre se não nascer aqui.
        dimensions=dimensoes or None,
        recommendations=recomendacoes or None,
        evidence=evidencias or None,
        **_publicar_familias_analiticas(facts),
    )
    return AssemblyV3Outcome(public_result=publico)
