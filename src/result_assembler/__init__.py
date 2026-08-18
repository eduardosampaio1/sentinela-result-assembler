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

from collections.abc import Mapping

from pydantic import ValidationError

from result_assembler.assembler.assemble import AssemblyOutcome, assemble
from result_assembler.assembler.assemble_v3 import AssemblyV3Outcome, assemble_v3
from result_assembler.assembler.assemble_v2 import (
    AssemblyOutcomeV2,
    RecordCountMismatch,
    assemble_v2,
)
from result_assembler.contracts.analytics import AnalyticsComponent, ComponentStatus
from result_assembler.contracts.facts import (
    AnalysisFacts,
    AnalysisFactsV2,
    AnalysisFactsV3,
    AnalysisWindow,
    Availability,
    CalculationProvenance,
    Denominator,
    FactAlert,
    FactDimension,
    FactEvidenceSummary,
    FactExecutiveSummary,
    FactIndicator,
    FactIntent,
    FactIssue,
    FactMedida,
    FactMethod,
    FactProjection,
    FactRecommendation,
    FactRisk,
    FactScore,
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
    FACTS_SCHEMA_V2_VERSION,
    FACTS_SCHEMA_V3_VERSION,
    FACTS_SCHEMA_VERSION,
    RESULT_SCHEMA_V2_VERSION,
    RESULT_SCHEMA_VERSION,
    SUPPORTED_FACTS_SCHEMA_VERSIONS,
    SUPPORTED_MEASUREMENT_CONTRACT_VERSIONS,
)


def _campos_contratados() -> frozenset[str]:
    """Nomes de campo que existem em algum modelo de `analysis-facts-*`.

    As familias do v2 e do v3 entram: sem elas, um erro em `scores[0].value` sairia com o
    segmento mascarado, e o log deixaria de dizer ONDE o produtor errou — que e a unica
    coisa que esta funcao existe para preservar.
    """
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
        AnalysisFactsV2,
        FactAlert,
        FactIssue,
        FactExecutiveSummary,
        AnalysisFactsV3,
        FactMedida,
        FactScore,
        FactRisk,
        FactProjection,
        FactIntent,
        FactMethod,
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


#: Qual classe lê qual versão do documento. É a porta despachando, e não adivinhando.
#:
#: Antes daqui `parse_facts` fixava `AnalysisFacts` — a classe do v1 — e como o contrato é
#: `extra="forbid"`, um documento v2 ou v3 era RECUSADO por trazer campos que o v1 não
#: declara. Medido: `parse_facts` sobre um documento v2 devolvia `SchemaMismatch`. As
#: famílias do v2 e do v3 existiam no contrato e não tinham por onde entrar.
#:
#: A regra que este mapa implementa é uma só: **o objeto nunca é mais estreito que o
#: documento**. Parsear um documento que declara v3 como v1 não é perda de campo — é o
#: assembler publicando `scores: null` ("ninguém produziu") sobre um documento que trazia
#: scores. Uma mentira, no vocabulário exato que o contrato existe para proteger.
#:
#: O caminho inverso é legítimo e NÃO é bloqueado: o montador do v1 lendo um objeto v3
#: publica a visão do v1, mais estreita por contrato. Os dois montadores leem o MESMO
#: objeto de propósito — resolver a referência duas vezes abriria a janela para os dois
#: documentos descreverem estados diferentes da mesma análise.
_CLASSE_POR_VERSAO: dict[str, type[AnalysisFacts]] = {
    FACTS_SCHEMA_VERSION: AnalysisFacts,
    FACTS_SCHEMA_V2_VERSION: AnalysisFactsV2,
    FACTS_SCHEMA_V3_VERSION: AnalysisFactsV3,
}


def parse_facts(payload: object) -> AnalysisFacts:
    """`dict` cru → `AnalysisFacts` da versão que o documento DECLARA.

    Existe porque `model_validate` levanta `pydantic.ValidationError` (Codex R2 [5]):
    campo extra, `NaN`, bool ou string numérica escapariam de um `except AssemblyError`.
    Nem a mensagem nem a localização ecoam conteúdo do payload — e a versão declarada É
    payload, então ela também não aparece no erro.

    Falha FECHADA: versão que este assembler não sabe ler é recusada, nunca lida "no melhor
    esforço" pela classe mais próxima.
    """
    versao = payload.get("facts_schema_version") if isinstance(payload, Mapping) else None
    modelo = _CLASSE_POR_VERSAO.get(versao) if isinstance(versao, str) else None
    if modelo is None:
        raise SchemaMismatch(
            "versão de facts não suportada", location="facts_schema_version"
        )
    try:
        return modelo.model_validate(payload)
    except ValidationError as exc:
        locais = sorted({_local_seguro(tuple(e["loc"])) for e in exc.errors()})
        raise SchemaMismatch(
            "payload não corresponde à versão que declara",
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
    "FACTS_SCHEMA_V2_VERSION",
    "FACTS_SCHEMA_V3_VERSION",
    "FACTS_SCHEMA_VERSION",
    "INDICATOR_REGISTRY",
    "INDICATOR_REGISTRY_VERSION",
    "RESULT_SCHEMA_V2_VERSION",
    "RESULT_SCHEMA_VERSION",
    "SUPPORTED_DIMENSION_IDS",
    "SUPPORTED_FACTS_SCHEMA_VERSIONS",
    "SUPPORTED_MEASUREMENT_CONTRACT_VERSIONS",
    "AnalysisFacts",
    "AnalysisFactsV2",
    "AnalysisFactsV3",
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
    "FactAlert",
    "FactDimension",
    "FactExecutiveSummary",
    "FactIntent",
    "FactIssue",
    "FactMedida",
    "FactMethod",
    "FactProjection",
    "FactRisk",
    "FactScore",
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
    "assemble_v3",
    "AssemblyV3Outcome",
    "assemble_v2",
    "checksum",
    "parse_facts",
    "serialize_canonical",
    "to_canonical_dict",
    "validate_evidence_safety",
    "validate_facts",
    "validate_result",
]
