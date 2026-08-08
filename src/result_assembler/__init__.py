"""Canonical Result Assembler — o montador oficial do resultado público do ARGOS.

    Assembler organizes facts. Assembler does not calculate analytics.

Biblioteca pura: sem FastAPI, sem banco, sem Redis, sem fila, sem filesystem
compartilhado, sem variável de ambiente. Recebe fatos já calculados pelo domínio
analítico e devolve o documento público canônico mais um manifesto interno.

Uso mínimo::

    from result_assembler import assemble, parse_facts, serialize_canonical

    facts = parse_facts(payload)          # levanta SchemaMismatch (AssemblyError)
    outcome = assemble(facts)             # levanta AssemblyError específico
    bytes_canonicos = serialize_canonical(outcome.public_result)

`parse_facts` é a porta recomendada: `AnalysisFacts.model_validate` levanta
`pydantic.ValidationError`, que NÃO é `AssemblyError` — um consumidor que capturasse só
as categorias tipadas da biblioteca perderia campo extra, `NaN` e tipo errado.
"""

from __future__ import annotations

from pydantic import ValidationError

from result_assembler.assembler.assemble import AssemblyOutcome, assemble
from result_assembler.assembler.assemble_v2 import (
    AssemblyOutcomeV2,
    RecordCountMismatch,
    assemble_v2,
)
from result_assembler.contracts.analytics import AnalyticsComponent, ComponentStatus
from result_assembler.contracts.facts import (
    AnalysisFacts,
    AnalysisWindow,
    Availability,
    CalculationProvenance,
    Denominator,
    FactDimension,
    FactEvidenceSummary,
    FactIndicator,
    FactRecommendation,
    FactsIdentity,
    IndicatorKind,
    Reason,
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
from result_assembler.contracts.result_v2 import (
    PublicAnalyticsBlock,
    PublicResultV2,
    PublicSummaryV2,
)
from result_assembler.errors import (
    AssemblyError,
    AssemblyInvariantViolation,
    DuplicateIndicator,
    InvalidDenominator,
    InvalidUnit,
    InvalidValue,
    MissingRequiredFact,
    SchemaMismatch,
    UnknownIndicator,
    UnsafeEvidence,
    UnsupportedFactsVersion,
    UnsupportedMeasurementVersion,
)
from result_assembler.registry.indicators import (
    CANONICAL_ORDER,
    INDICATOR_REGISTRY,
    INDICATOR_REGISTRY_VERSION,
    SUPPORTED_DIMENSION_IDS,
    IndicatorDefinition,
)
from result_assembler.serialization.canonical import (
    CHECKSUM_ALGORITHM,
    checksum,
    serialize_canonical,
    to_canonical_dict,
)
from result_assembler.validation.invariants import validate_facts
from result_assembler.validation.safety import validate_evidence_safety
from result_assembler.version import (
    ASSEMBLER_VERSION,
    FACTS_SCHEMA_VERSION,
    RESULT_SCHEMA_V2_VERSION,
    RESULT_SCHEMA_VERSION,
    SUPPORTED_FACTS_SCHEMA_VERSIONS,
    SUPPORTED_MEASUREMENT_CONTRACT_VERSIONS,
)


def _campos_contratados() -> frozenset[str]:
    """Nomes de campo que existem em algum modelo de `analysis-facts-v1`."""
    modelos = (
        AnalysisFacts,
        FactsIdentity,
        AnalysisWindow,
        CalculationProvenance,
        FactIndicator,
        FactDimension,
        FactRecommendation,
        FactEvidenceSummary,
        Denominator,
    )
    return frozenset(campo for m in modelos for campo in m.model_fields)


_CAMPOS_CONTRATADOS = _campos_contratados()

#: Substituto para segmento de caminho que veio do payload e não é campo contratado.
_SEGMENTO_OCULTO = "<campo-nao-contratado>"


def _local_seguro(loc: tuple[object, ...]) -> str:
    """Caminho do erro sem ecoar texto controlado pelo payload.

    O `loc` do pydantic inclui a **chave** do campo extra — e a chave é payload
    (Codex R5 [1]). Um envelope com `{"Bearer sk-live-...": 1}` colocaria o token na
    localização do erro, que é justamente o que vai para o log. Índices e nomes
    contratados passam; o resto vira marcador.
    """
    partes: list[str] = []
    for p in loc:
        if isinstance(p, int):
            partes.append(str(p))
        elif isinstance(p, str) and p in _CAMPOS_CONTRATADOS:
            partes.append(p)
        else:
            partes.append(_SEGMENTO_OCULTO)
    return ".".join(partes)


def parse_facts(payload: object) -> AnalysisFacts:
    """`dict` cru → `AnalysisFacts`, com erro da FAMÍLIA da biblioteca.

    Existe porque `model_validate` levanta `pydantic.ValidationError` (Codex R2 [5]):
    campo extra, `NaN`, bool ou string numérica escapariam de um `except AssemblyError`.
    Nem a mensagem nem a localização ecoam conteúdo do payload.
    """
    try:
        return AnalysisFacts.model_validate(payload)
    except ValidationError as exc:
        locais = sorted({_local_seguro(tuple(e["loc"])) for e in exc.errors()})
        raise SchemaMismatch(
            f"payload não corresponde a {FACTS_SCHEMA_VERSION}",
            location="; ".join(locais[:5]),
        ) from None


def validate_result(result: PublicResult) -> None:
    """Revalida um resultado público já montado.

    Existe para o consumidor conferir o que recebeu sem depender de ter os fatos: o
    contrato é estrito (`extra="forbid"`), então revalidar é reconstruir pelo modelo.
    """
    PublicResult.model_validate(result.model_dump(mode="json"))


__all__ = [
    "ASSEMBLER_VERSION",
    "CANONICAL_ORDER",
    "CHECKSUM_ALGORITHM",
    "FACTS_SCHEMA_VERSION",
    "INDICATOR_REGISTRY",
    "INDICATOR_REGISTRY_VERSION",
    "RESULT_SCHEMA_V2_VERSION",
    "RESULT_SCHEMA_VERSION",
    "SUPPORTED_DIMENSION_IDS",
    "SUPPORTED_FACTS_SCHEMA_VERSIONS",
    "SUPPORTED_MEASUREMENT_CONTRACT_VERSIONS",
    "AnalysisFacts",
    "AnalysisWindow",
    "AnalyticsComponent",
    "AssemblyError",
    "AssemblyInvariantViolation",
    "AssemblyOutcome",
    "AssemblyOutcomeV2",
    "Availability",
    "CalculationProvenance",
    "ComponentStatus",
    "Denominator",
    "DuplicateIndicator",
    "FactDimension",
    "FactEvidenceSummary",
    "FactIndicator",
    "FactRecommendation",
    "FactsIdentity",
    "IndicatorDefinition",
    "IndicatorKind",
    "IndicatorState",
    "InternalManifest",
    "InvalidDenominator",
    "InvalidUnit",
    "InvalidValue",
    "MissingRequiredFact",
    "Partiality",
    "PublicAnalyticsBlock",
    "PublicDenominator",
    "PublicDimension",
    "PublicEvidenceSummary",
    "PublicIndicator",
    "PublicRecommendation",
    "PublicResult",
    "PublicResultV2",
    "PublicSummary",
    "PublicSummaryV2",
    "Reason",
    "RecordCountMismatch",
    "SchemaMismatch",
    "UnknownIndicator",
    "UnsafeEvidence",
    "UnsupportedFactsVersion",
    "UnsupportedMeasurementVersion",
    "VersionsSeen",
    "assemble",
    "assemble_v2",
    "checksum",
    "parse_facts",
    "serialize_canonical",
    "to_canonical_dict",
    "validate_evidence_safety",
    "validate_facts",
    "validate_result",
]
