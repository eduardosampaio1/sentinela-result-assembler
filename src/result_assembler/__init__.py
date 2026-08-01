"""Canonical Result Assembler — o montador oficial do resultado público do ARGOS.

    Assembler organizes facts. Assembler does not calculate analytics.

Biblioteca pura: sem FastAPI, sem banco, sem Redis, sem fila, sem filesystem
compartilhado, sem variável de ambiente. Recebe fatos já calculados pelo domínio
analítico e devolve o documento público canônico mais um manifesto interno.

Uso mínimo::

    from result_assembler import assemble, AnalysisFacts, serialize_canonical

    facts = AnalysisFacts.model_validate(payload)
    outcome = assemble(facts)
    bytes_canonicos = serialize_canonical(outcome.public_result)
"""

from __future__ import annotations

from result_assembler.assembler.assemble import AssemblyOutcome, assemble
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
    RESULT_SCHEMA_VERSION,
    SUPPORTED_FACTS_SCHEMA_VERSIONS,
    SUPPORTED_MEASUREMENT_CONTRACT_VERSIONS,
)


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
    "RESULT_SCHEMA_VERSION",
    "SUPPORTED_DIMENSION_IDS",
    "SUPPORTED_FACTS_SCHEMA_VERSIONS",
    "SUPPORTED_MEASUREMENT_CONTRACT_VERSIONS",
    "AnalysisFacts",
    "AnalysisWindow",
    "AssemblyError",
    "AssemblyInvariantViolation",
    "AssemblyOutcome",
    "Availability",
    "CalculationProvenance",
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
    "PublicDenominator",
    "PublicDimension",
    "PublicEvidenceSummary",
    "PublicIndicator",
    "PublicRecommendation",
    "PublicResult",
    "PublicSummary",
    "Reason",
    "SchemaMismatch",
    "UnknownIndicator",
    "UnsafeEvidence",
    "UnsupportedFactsVersion",
    "UnsupportedMeasurementVersion",
    "VersionsSeen",
    "assemble",
    "checksum",
    "serialize_canonical",
    "to_canonical_dict",
    "validate_evidence_safety",
    "validate_facts",
    "validate_result",
]
