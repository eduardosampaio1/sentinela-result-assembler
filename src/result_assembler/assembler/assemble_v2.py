"""`analysis-facts-v1` + projeção pública → `analysis-result-v2` (MF6.2 + MF6.3).

Biblioteca **pura**, como o v1: sem storage, sem rede, sem relógio. Os dois insumos chegam
resolvidos, e a única coisa que este módulo acrescenta ao v1 é o que só existe quando há dois —
o bloco analítico e a **reconciliação das contagens**.

## As três contagens, e por que só duas se comparam

    A  janela da Engine        `summary.engine_window_record_count`   (v1: `summary.record_count`)
    B  conversas consideradas  indicador `observed_conversations`
    C  denominador analítico   `analytics.record_count`

**B e C têm a MESMA semântica declarada** — as duas são "número de conversas" sobre o mesmo
dataset canônico, e o Analytics congelou `record_count ≡ número de conversas` (MF5-FUND). Se as
duas descrevem o mesmo dataset, `B == C` **deve** valer, e divergência é defeito, não nuance:
`RecordCountMismatch`, e nenhum documento nasce.

**A é diferente de C, e o v1 escondia isso** dando-lhes o mesmo nome. No v2 elas têm nomes
próprios e nunca são comparadas — comparar a janela da Engine com o denominador analítico
recusaria montagens perfeitamente corretas.

## Por que a divergência RECUSA em vez de escolher

Publicar uma das duas seria escolher em silêncio qual fonte está certa, e a errada apareceria
como número num painel. Recusar é o único desfecho que não mente — e é o que o congelamento da
MF6.3 exige.
"""

from __future__ import annotations

from dataclasses import dataclass

from result_assembler.assembler.assemble import (
    WITHHELD_INTERNAL_FIELDS,
    _avisos,
    _ordem_canonica,
    _partialidade,
    _publicar_dimensao,
    _publicar_indicador,
)
from result_assembler.contracts.analytics import AnalyticsComponent, ComponentStatus
from result_assembler.contracts.facts import AnalysisFacts
from result_assembler.contracts.manifest import InternalManifest, VersionsSeen
from result_assembler.contracts.result import (
    IndicatorState,
    PublicEvidenceSummary,
    PublicIndicator,
    PublicRecommendation,
)
from result_assembler.contracts.result_v2 import (
    PublicAnalyticsBlock,
    PublicResultV2,
    PublicSummaryV2,
)
from result_assembler.errors import AssemblyError, AssemblyInvariantViolation
from result_assembler.registry.indicators import (
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
    RESULT_SCHEMA_V2_VERSION,
)

#: O id do FATO que carrega a contagem B. O id PÚBLICO dele é outro
#: (`analyzed_conversation_count`), e é por isso que ele é resolvido pelo REGISTRO em vez de
#: escrito à mão.
#:
#: **A primeira versão deste módulo tinha o literal errado aqui** — usava o id do fato para
#: procurar entre os indicadores PÚBLICOS. O laço nunca achava nada, `_conversas_observadas`
#: devolvia `None`, e a invariante B == C passava sempre, sem comparar coisa nenhuma. Uma trava
#: que nunca dispara é pior que trava nenhuma: ela dá a impressão de que alguém está olhando.
_ID_DO_FATO_DAS_CONVERSAS = "observed_conversations"


def _id_publico_das_conversas() -> str:
    """O id público, resolvido pelo registro. Fail-closed se o indicador sair do vocabulário."""
    defin = definicao_de(_ID_DO_FATO_DAS_CONVERSAS)
    if defin is None:  # pragma: no cover - o registro é congelado por teste próprio
        raise AssemblyInvariantViolation(
            "o indicador da contagem de conversas saiu do registro: a invariante B == C ficaria "
            "sem lado esquerdo, e passaria por vacuidade"
        )
    return defin.public_id


class RecordCountMismatch(AssemblyError):
    """**B ≠ C.** Duas fontes descrevem o mesmo dataset e discordam sobre quantas conversas há.

    Nunca resolvido escolhendo uma: a errada apareceria como número num painel, e ninguém teria
    como saber qual foi. A mensagem carrega os DOIS valores porque eles são contagens agregadas —
    não são conteúdo de cliente, e sem eles o diagnóstico começa do zero.
    """

    def __init__(self, observadas: float, denominador: int) -> None:
        self.observadas = observadas
        self.denominador = denominador
        super().__init__(
            f"observed_conversations={observadas:g} difere do record_count analítico="
            f"{denominador}: as duas afirmam o número de conversas do mesmo dataset"
        )


@dataclass(frozen=True)
class AssemblyOutcomeV2:
    """O documento integrado e o registro técnico. Mesma forma do v1."""

    public_result: PublicResultV2
    internal_manifest: InternalManifest


def _conversas_observadas(publico_indicadores: tuple[PublicIndicator, ...]) -> float | None:
    """A contagem B, se ela foi MEDIDA. `None` quando não há o que comparar.

    Indicador não medido não entra na invariante: exigir igualdade contra um valor que o domínio
    declarou indisponível recusaria montagens corretas — e transformaria "não deu para medir" em
    "os dois lados discordam", que são coisas opostas.
    """
    for ind in publico_indicadores:
        if ind.id == _id_publico_das_conversas():
            return ind.value if ind.state is IndicatorState.MEASURED else None
    return None


def reconciliar_contagens(
    publico_indicadores: tuple[PublicIndicator, ...], analytics: AnalyticsComponent
) -> None:
    """A invariante **B == C**. Levanta `RecordCountMismatch`, ou passa em silêncio.

    Só compara quando as duas existem: `withheld` não traz denominador, e um indicador não medido
    não traz contagem. Nos dois casos não há discordância — há ausência, que é outra coisa.
    """
    if analytics.record_count is None:
        return
    observadas = _conversas_observadas(publico_indicadores)
    if observadas is None:
        return
    if int(observadas) != int(analytics.record_count):
        raise RecordCountMismatch(observadas, analytics.record_count)


def assemble_v2(facts: AnalysisFacts, analytics: AnalyticsComponent) -> AssemblyOutcomeV2:
    """Os dois insumos → `analysis-result-v2`.

    A montagem do v1 é REUSADA inteira para a parte da Engine — indicadores, dimensões,
    recomendações, evidência e parcialidade saem das mesmas funções. Reimplementá-las aqui daria
    dois documentos que divergiriam no primeiro ajuste de ordenação, e o `result_checksum` de cada
    um passaria a descrever uma montagem diferente.

    Não existe montagem "no melhor esforço": qualquer irregularidade levanta, e nenhum documento
    parcial é devolvido.
    """
    validate_facts(facts)
    validate_evidence_safety(facts)

    indicadores = tuple(_publicar_indicador(ind) for ind in _ordem_canonica(facts))
    reconciliar_contagens(indicadores, analytics)

    dimensoes = tuple(_publicar_dimensao(d) for d in sorted(facts.dimensions, key=lambda d: d.id))
    recomendacoes = tuple(
        PublicRecommendation(
            id=r.id,
            title=r.title,
            priority=r.priority,
            category=r.category,
            evidence_refs=tuple(sorted(r.evidence_refs)),
        )
        for r in sorted(facts.recommendations, key=lambda r: r.order)
    )
    evidencias = tuple(
        PublicEvidenceSummary(id=e.id, kind=e.kind, observed_count=e.observed_count, label=e.label)
        for e in sorted(facts.evidence, key=lambda e: e.id)
    )

    publico = PublicResultV2(
        analysis_id=facts.identity.analysis_id,
        result_schema_version=RESULT_SCHEMA_V2_VERSION,
        measurement_contract_version=facts.measurement_contract_version,
        summary=PublicSummaryV2(
            # O nome MUDA aqui, e o valor não: continua sendo a janela que a Engine analisou.
            engine_window_record_count=facts.window.record_count,
            analyzed_at=facts.window.analyzed_at,
        ),
        indicators=indicadores,
        dimensions=dimensoes,
        recommendations=recomendacoes,
        evidence=evidencias,
        partiality=_partialidade(indicadores),
        analytics=PublicAnalyticsBlock(
            component_status=analytics.component_status,
            projection_digest=analytics.projection_digest,
            snapshot_contract_version=analytics.snapshot_contract_version,
            record_count=analytics.record_count,
            # Transportado, nunca interpretado. Recalcular disclosure aqui seria decidir de novo
            # o que o Privacy Gate já decidiu, e num lugar que não tem os dados para isso.
            data=analytics.data,
        ),
    )

    manifesto = InternalManifest(
        analysis_id=facts.identity.analysis_id,
        versions=VersionsSeen(
            assembler_version=ASSEMBLER_VERSION,
            facts_schema_version=FACTS_SCHEMA_VERSION,
            result_schema_version=RESULT_SCHEMA_V2_VERSION,
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
        warnings=_avisos_v2(publico),
        result_checksum=checksum(serialize_canonical(publico)),
        checksum_algorithm=CHECKSUM_ALGORITHM,
    )
    return AssemblyOutcomeV2(public_result=publico, internal_manifest=manifesto)


def _avisos_v2(publico: PublicResultV2) -> tuple[str, ...]:
    """Os avisos do v1, mais o que só o documento integrado pode observar.

    `analytics_withheld` é AVISO e não erro, e a distinção é a decisão inteira da MF5: disclosure
    é conclusão, não defeito. Ele existe para que quem lê o manifesto saiba por que o bloco veio
    sem conteúdo, sem ter de inferir do `null`.
    """
    avisos = list(_avisos(publico))  # `_avisos` só lê campos que o v2 também tem
    if publico.analytics.component_status is ComponentStatus.WITHHELD:
        avisos.append("analytics_withheld")
    elif publico.analytics.component_status is ComponentStatus.PARTIAL:
        avisos.append("analytics_partial")
    return tuple(sorted(avisos))


__all__ = [
    "AssemblyOutcomeV2",
    "RecordCountMismatch",
    "assemble_v2",
    "reconciliar_contagens",
]
