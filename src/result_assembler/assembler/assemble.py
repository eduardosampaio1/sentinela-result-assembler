"""A montagem.

Organiza fatos. Não calcula analítica.

Tudo aqui é função pura de `AnalysisFacts`: sem relógio, sem aleatoriedade, sem I/O, sem
estado global. A única "decisão" que o assembler toma é a ordem de publicação — e ela vem
do registro (indicadores) ou do próprio domínio (recomendações), nunca da ordem em que os
fatos chegaram.
"""

from __future__ import annotations

from dataclasses import dataclass

from result_assembler.contracts.facts import (
    AnalysisFacts,
    Availability,
    FactDimension,
    FactIndicator,
)
from result_assembler.contracts.manifest import InternalManifest, VersionsSeen
from result_assembler.contracts.result import (
    IndicatorState,
    Partiality,
    PublicDenominator,
    PublicDimension,
    PublicEvidenceSummary,
    PublicIndicator,
    PublicRecommendation,
    PublicResult,
    PublicSummary,
)
from result_assembler.errors import UnknownIndicator
from result_assembler.registry.indicators import (
    CANONICAL_ORDER,
    INDICATOR_REGISTRY_VERSION,
    definicao_de,
)
from result_assembler.serialization.canonical import (
    CHECKSUM_ALGORITHM,
    checksum,
    serialize_canonical,
)
from result_assembler.validation.invariants import validate_facts
from result_assembler.validation.safety import validate_evidence_safety
from result_assembler.version import (
    ASSEMBLER_VERSION,
    FACTS_SCHEMA_VERSION,
    RESULT_SCHEMA_VERSION,
)

#: Disponibilidade interna → estado público. Tabela explícita: um `if` encadeado aqui
#: seria o lugar onde "não medido" vira "zero" numa refatoração distraída.
_ESTADO_PUBLICO: dict[Availability, IndicatorState] = {
    Availability.AVAILABLE: IndicatorState.MEASURED,
    Availability.PARTIAL: IndicatorState.PARTIALLY_MEASURED,
    Availability.UNAVAILABLE: IndicatorState.NOT_MEASURED,
    Availability.NOT_EVALUABLE: IndicatorState.NOT_APPLICABLE,
    Availability.FAILED: IndicatorState.CALCULATION_FAILED,
}

#: Motivo público por estado não-completo. Ordenado depois; o texto é estável.
_MOTIVO_POR_ESTADO: dict[IndicatorState, str] = {
    IndicatorState.PARTIALLY_MEASURED: "indicator_partially_measured",
    IndicatorState.NOT_MEASURED: "indicator_not_measured",
    IndicatorState.NOT_APPLICABLE: "indicator_not_applicable",
    IndicatorState.CALCULATION_FAILED: "indicator_calculation_failed",
}

#: Campos recebidos que a fronteira segura NÃO publica. Declarado, não implícito.
WITHHELD_INTERNAL_FIELDS: tuple[str, ...] = (
    "identity.analysis_run_id",
    "identity.job_id",
    "indicators[].calculation_version",
    "indicators[].expected_units",
    "indicators[].observed_units",
    "indicators[].reason",
    "indicators[].source",
    "provenance.analysis_version",
    "provenance.dataset_fingerprint",
    "provenance.engine_version",
)


@dataclass(frozen=True)
class AssemblyOutcome:
    """O que a montagem devolve: o documento público e o registro técnico."""

    public_result: PublicResult
    internal_manifest: InternalManifest


def _publicar_indicador(ind: FactIndicator) -> PublicIndicator:
    defin = definicao_de(ind.id)
    if defin is None:  # pragma: no cover - `validate_facts` já recusou antes
        raise UnknownIndicator("indicador não registrado")

    estado = _ESTADO_PUBLICO[ind.availability]
    denom = (
        PublicDenominator(kind=ind.denominator.kind, value=ind.denominator.value)
        if ind.denominator is not None
        else None
    )
    return PublicIndicator(
        id=defin.public_id,
        state=estado,
        # O valor sai como o domínio calculou. Nenhum arredondamento é aplicado aqui:
        # `display_precision` viaja ao lado como SUGESTÃO, e o sub-centavo sobrevive.
        value=ind.value,
        kind=defin.kind.value,
        unit=defin.unit,
        currency=ind.currency,
        denominator=denom,
        # Cobertura só faz sentido — e só é publicada — quando a medição é parcial.
        coverage=ind.data_coverage if estado is IndicatorState.PARTIALLY_MEASURED else None,
        display_precision=defin.display_precision,
    )


def _publicar_dimensao(dim: FactDimension) -> PublicDimension:
    estado = _ESTADO_PUBLICO[dim.availability]
    return PublicDimension(
        id=dim.id,
        state=estado,
        value=dim.value,
        coverage=dim.data_coverage if estado is IndicatorState.PARTIALLY_MEASURED else None,
    )


def _ordem_canonica(facts: AnalysisFacts) -> tuple[FactIndicator, ...]:
    """Ordena pela ordem CONTRATADA, não pela ordem de chegada.

    Dois produtores que mediram a mesma coisa precisam gerar os mesmos bytes; se a ordem
    viesse do payload, o checksum viraria função de quem montou o dict.
    """
    por_id = {ind.id: ind for ind in facts.indicators}
    return tuple(por_id[i] for i in CANONICAL_ORDER if i in por_id)


def _partialidade(indicadores: tuple[PublicIndicator, ...]) -> Partiality:
    motivos = {
        _MOTIVO_POR_ESTADO[i.state] for i in indicadores if i.state in _MOTIVO_POR_ESTADO
    }
    return Partiality(complete=not motivos, reasons=tuple(sorted(motivos)))


def assemble(facts: AnalysisFacts) -> AssemblyOutcome:
    """`analysis-facts-v1` → resultado público + manifesto interno.

    Levanta `AssemblyError` (subclasse específica) em qualquer irregularidade. Não existe
    montagem "no melhor esforço": um resultado público montado sobre fato irregular é pior
    que resultado nenhum, porque parece confiável.
    """
    validate_facts(facts)
    validate_evidence_safety(facts)

    indicadores = tuple(_publicar_indicador(ind) for ind in _ordem_canonica(facts))
    dimensoes = tuple(
        _publicar_dimensao(d) for d in sorted(facts.dimensions, key=lambda d: d.id)
    )
    # A ordem é a do DOMÍNIO (`order`), que já rankeou. O assembler não reordena por
    # impacto, não escolhe a principal e não gera headline.
    recomendacoes = tuple(
        PublicRecommendation(
            id=r.id,
            title=r.title,
            priority=r.priority,
            category=r.category,
            # ORDENADO: `evidence_refs` é um CONJUNTO de referências, não uma sequência
            # com significado — diferente de `recommendations`, onde `order` é intenção
            # declarada do domínio. Sem ordenar (Codex R2 [4]), duas entradas
            # semanticamente iguais gerariam checksums diferentes.
            evidence_refs=tuple(sorted(r.evidence_refs)),
        )
        for r in sorted(facts.recommendations, key=lambda r: r.order)
    )
    evidencias = tuple(
        PublicEvidenceSummary(
            id=e.id, kind=e.kind, observed_count=e.observed_count, label=e.label
        )
        for e in sorted(facts.evidence, key=lambda e: e.id)
    )

    publico = PublicResult(
        analysis_id=facts.identity.analysis_id,
        result_schema_version=RESULT_SCHEMA_VERSION,
        measurement_contract_version=facts.measurement_contract_version,
        summary=PublicSummary(
            record_count=facts.window.record_count,
            # Vem do fato. O assembler não tem relógio — ver ADR-005.
            analyzed_at=facts.window.analyzed_at,
        ),
        indicators=indicadores,
        dimensions=dimensoes,
        recommendations=recomendacoes,
        evidence=evidencias,
        partiality=_partialidade(indicadores),
    )

    manifesto = InternalManifest(
        analysis_id=facts.identity.analysis_id,
        versions=VersionsSeen(
            assembler_version=ASSEMBLER_VERSION,
            facts_schema_version=FACTS_SCHEMA_VERSION,
            result_schema_version=RESULT_SCHEMA_VERSION,
            measurement_contract_version=facts.measurement_contract_version,
            indicator_registry_version=INDICATOR_REGISTRY_VERSION,
        ),
        job_id=facts.identity.job_id,
        analysis_run_id=facts.identity.analysis_run_id,
        engine_version=facts.provenance.engine_version,
        analysis_version=facts.provenance.analysis_version,
        dataset_fingerprint=facts.provenance.dataset_fingerprint,
        accepted_indicator_ids=tuple(i.id for i in indicadores),
        withheld_internal_fields=WITHHELD_INTERNAL_FIELDS,
        warnings=_avisos(publico),
        result_checksum=checksum(serialize_canonical(publico)),
        checksum_algorithm=CHECKSUM_ALGORITHM,
    )
    return AssemblyOutcome(public_result=publico, internal_manifest=manifesto)


def _avisos(publico: PublicResult) -> tuple[str, ...]:
    """Observações não fatais. Ordenadas para o manifesto ser determinístico também."""
    avisos: list[str] = []
    if not publico.indicators:
        avisos.append("no_indicators_published")
    if not publico.recommendations:
        avisos.append("no_recommendations_published")
    if not publico.evidence:
        avisos.append("no_evidence_published")
    if not publico.partiality.complete:
        avisos.append("result_is_partial")
    return tuple(sorted(avisos))
