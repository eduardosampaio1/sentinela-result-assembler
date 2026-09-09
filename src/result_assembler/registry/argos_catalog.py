"""Catálogo nominal do ARGOS — a autoridade de PRODUTO, em código.

Este arquivo não descreve o que o pipeline faz hoje. Ele descreve o que o ARGOS **declara
produzir**, e existe para que a distância entre as duas coisas seja mensurável em vez de
descoberta por acidente três ondas depois.

## Por que ele existe

O discovery de 2026-08-12 mediu: das 34 métricas do documento *"Métricas do Sentinela
ARGOS"*, **8** chegavam ao contrato público. As outras 26 não foram recusadas por ninguém —
elas simplesmente não estavam na tabela de 14 ids de `engine/facts/producer.py`. Não havia
recusa, não havia decisão, não havia sinal: havia ausência silenciosa.

O defeito estrutural não era nenhuma métrica em particular. Era **não existir nada que
comparasse o que o motor produz com o que o produto publica**. Este catálogo é esse algo.

## O que ele NÃO é

Não é registro de indicador (isso é `indicators.py`, e ele decide se um fato pode virar
indicador público). Não é schema. Não calcula, não converte, não valida valor. Ele é uma
LISTA NOMINAL com a família de destino de cada output — e a aritmética que prova que a
lista está inteira.

## A regra da família única

Cada output mora em exatamente uma família. É o que impede o erro que a primeira versão
desta spec cometeu: `Response Variance` aparecia como score global **e** como
`mean_response_variance_per_intent` em indicadores. São a mesma métrica do catálogo em duas
roupas — um alias implícito, que infla a contagem e faz parecer que há mais publicação do
que existe. O gate reprova isso pela unicidade do `public_id`.

## Os 46

34 do documento oficial + 5 descobertas no contrato público durante o discovery
(`outcome_field_coverage_rate`, `conversion_rate`, `conversion_count`, `handoff_count`,
`cost_per_session`). As cinco são ARGOS legítimas — vêm de
`estimate_useful_outcome_economics` / `compute_tenant_metrics` e passam pelo allow-list de
`source` —, apenas nunca foram descritas no documento. Sete sinais de qualidade
conversacional observável foram adicionados no catálogo 1.1. Nenhum substitui as 34.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

#: Versão do catálogo. Muda quando um output entra, sai, muda de família ou de estado.
ARGOS_CATALOG_VERSION = "argos-catalog-1.1"

#: Quantos vieram do documento oficial, e quantos foram descobertos no contrato.
DOCUMENTADAS = 34
DESCOBERTAS = 12


class Familia:
    """Destino público do output. Não é tipo de dado — é *natureza semântica*.

    A separação existe porque achatar tudo em `indicators[]` foi exatamente o que produziu
    o contrato incompleto: score global, dimensão de saúde, métrica por intenção, risco e
    projeção não têm a mesma forma, e forçá-los ao mesmo envelope perde informação que o
    produtor tinha.
    """

    SCORES = "scores"
    DIMENSIONS = "dimensions"
    INDICATORS = "indicators"
    INTENTS = "intents"
    RISKS = "risks"
    PROJECTIONS = "projections"
    METHOD = "method"
    #: Não é família de publicação: é ausência DECLARADA, com motivo.
    BLOCKED = "blocked"


TODAS_AS_FAMILIAS = frozenset(
    {
        Familia.SCORES,
        Familia.DIMENSIONS,
        Familia.INDICATORS,
        Familia.INTENTS,
        Familia.RISKS,
        Familia.PROJECTIONS,
        Familia.METHOD,
        Familia.BLOCKED,
    }
)


class Bloqueio:
    """Por que um output catalogado não é publicado.

    Um bloqueio é **decisão registrada**, e é o oposto de ausência silenciosa. Ele aparece
    no catálogo, o gate o conta, e removê-lo exige mudar este arquivo — que é onde alguém
    olha.
    """

    #: O produtor mede outra coisa que não o que o nome promete. Envelope não conserta
    #: semântica: `Measurement` resolve "ausência virou zero", não "métrica errada".
    SEMANTICA_DE_MEDIDA = "BLOCKED_BY_MEASUREMENT_SEMANTICS"


@dataclass(frozen=True)
class OutputArgos:
    """Um output quantitativo declarado pelo ARGOS."""

    numero: int
    """Posição nominal, 1..46. Contígua por construção — o gate verifica."""

    nome: str
    """Nome do catálogo de produto, como a pessoa o lê."""

    familia: str
    """Destino público. Exatamente um."""

    public_id: str
    """Identidade pública. Única no catálogo inteiro — é o que mata o alias implícito."""

    bloqueio: str | None = None
    """Preenchido se e somente se `familia == BLOCKED`."""

    nota: str = ""
    """Por que este output está onde está, quando não é óbvio."""


_CATALOGO: tuple[OutputArgos, ...] = (
    # ── Saúde e qualidade global ────────────────────────────────────────────────────────
    OutputArgos(1, "Behavior Score", Familia.SCORES, "behavior_score",
                nota="escore global; exige method_version para ser comparável"),
    OutputArgos(2, "AI Health Score", Familia.SCORES, "ai_health_score",
                nota="composto das 4 dimensões — NÃO é a quinta dimensão"),
    OutputArgos(3, "Consistency Score", Familia.SCORES, "consistency_score",
                nota="excluído no v1 por absence-as-zero; o envelope Measurement resolve"),
    OutputArgos(4, "Global Confidence", Familia.SCORES, "global_confidence",
                nota="confiança sobre a análise, não sobre o negócio"),
    OutputArgos(5, "Economic Health Score", Familia.DIMENSIONS, "economic"),
    OutputArgos(6, "Semantic Health Score", Familia.DIMENSIONS, "semantic"),
    OutputArgos(7, "Behavioral Health Score", Familia.DIMENSIONS, "behavioral"),
    OutputArgos(8, "Structural Health Score", Familia.DIMENSIONS, "structural"),
    # ── Comportamento e semântica ───────────────────────────────────────────────────────
    OutputArgos(9, "Token Waste", Familia.BLOCKED, "token_waste",
                bloqueio=Bloqueio.SEMANTICA_DE_MEDIDA,
                nota="produtor mede int(round(avg_tokens)), anotado `# proxy`; "
                     "o nome promete desperdício e a medida não o entrega"),
    OutputArgos(10, "Cross-Intent Similarity", Familia.SCORES, "cross_intent_similarity"),
    OutputArgos(11, "Response Variance", Familia.INDICATORS,
                "mean_response_variance_per_intent",
                nota="UM output. O detalhe por intenção vive em intents[] como grão fino "
                     "da MESMA métrica — não é entrada nova do catálogo"),
    OutputArgos(12, "Response Stability", Familia.SCORES, "response_stability",
                nota="escala 0..100 do produtor, publicada como tal (D5 do owner); "
                     "converter no bridge seria normalização não autorizada"),
    OutputArgos(13, "Intent Coverage", Familia.INDICATORS, "intent_coverage_rate"),
    OutputArgos(14, "Semantic Drift", Familia.SCORES, "semantic_drift",
                nota="medido DENTRO de uma análise; não é delta A×B da EVO-02"),
    OutputArgos(15, "Intent Score", Familia.INTENTS, "intent_score",
                nota="por intenção, com suporte amostral e severidade; achatar em "
                     "indicators[] perderia a identidade da intenção"),
    # ── Economia e eficiência ───────────────────────────────────────────────────────────
    OutputArgos(16, "Cost per Useful Outcome", Familia.INDICATORS, "cost_per_useful_outcome"),
    OutputArgos(17, "Useful Rate", Familia.INDICATORS, "useful_outcome_rate"),
    OutputArgos(18, "Useful Outcomes Observed", Familia.INDICATORS, "useful_outcome_count"),
    OutputArgos(19, "Observed Total Cost", Familia.INDICATORS, "total_estimated_cost"),
    OutputArgos(20, "Observed Token Cost", Familia.INDICATORS, "token_cost_total"),
    OutputArgos(21, "Observed Handoff Cost", Familia.INDICATORS, "handoff_cost_total"),
    OutputArgos(22, "Token Waste Cost", Familia.BLOCKED, "token_waste_cost",
                bloqueio=Bloqueio.SEMANTICA_DE_MEDIDA,
                nota="deriva de Token Waste; herda o bloqueio"),
    OutputArgos(23, "Estimated Handoff Cost", Familia.INDICATORS, "estimated_handoff_cost",
                nota="estimativa declarada — distinta das três observadas acima"),
    OutputArgos(24, "Containment Risk", Familia.RISKS, "containment_risk"),
    OutputArgos(25, "Conversion Risk", Familia.RISKS, "conversion_risk"),
    OutputArgos(26, "Projected Token Cost / Month", Familia.PROJECTIONS,
                "projected_token_cost@month",
                nota="horizonte é DADO; o `@` só desambigua a identidade no catálogo"),
    OutputArgos(27, "Projected Token Cost / Year", Familia.PROJECTIONS,
                "projected_token_cost@year"),
    OutputArgos(28, "Projected Handoff Cost / Month", Familia.PROJECTIONS,
                "projected_handoff_cost@month"),
    OutputArgos(29, "Projected Handoff Cost / Year", Familia.PROJECTIONS,
                "projected_handoff_cost@year"),
    # ── Volume, cobertura e suporte estatístico ─────────────────────────────────────────
    OutputArgos(30, "Conversations", Familia.INDICATORS, "analyzed_conversation_count"),
    OutputArgos(31, "Intents Detected", Familia.INDICATORS, "intents_detected_count",
                nota="hoje atravessa só como denominador `intents`; vira indicador próprio"),
    OutputArgos(32, "Covered Intents", Familia.INDICATORS, "covered_intents_count",
                nota="hoje é só numerador de intent_coverage_rate"),
    OutputArgos(33, "Min Samples / Intent", Familia.METHOD, "min_samples_per_intent",
                nota="PARÂMETRO do método, não medida observada"),
    OutputArgos(34, "Critical Alerts", Familia.INDICATORS, "critical_alert_count",
                nota="a CONTAGEM é métrica; o conteúdo dos alertas é família analítica"),
    # ── Descobertas no contrato público, ausentes do documento oficial ──────────────────
    OutputArgos(35, "Outcome Field Coverage Rate", Familia.INDICATORS,
                "outcome_field_coverage_rate",
                nota="mede presença do CAMPO outcome; renomeada no registry justamente "
                     "para não ser confundida com Intent Coverage"),
    OutputArgos(36, "Conversion Rate", Familia.INDICATORS, "conversion_rate",
                nota="o documento lista Conversion RISK, não a taxa medida"),
    OutputArgos(37, "Conversion Count", Familia.INDICATORS, "conversion_count"),
    OutputArgos(38, "Handoff Count", Familia.INDICATORS, "handoff_count",
                nota="o documento lista os CUSTOS de handoff, não a contagem"),
    OutputArgos(39, "Cost per Session", Familia.INDICATORS, "cost_per_session"),
    # ── Qualidade conversacional observável ────────────────────────────────────────────
    # Sinais lexicais versionados: úteis para localizar fricção, mas não equivalem a
    # sucesso de jornada. O catálogo mantém essa fronteira explícita.
    OutputArgos(40, "Empty Response Rate", Familia.INDICATORS, "empty_response_rate"),
    OutputArgos(41, "Error Response Rate", Familia.INDICATORS, "error_response_rate"),
    OutputArgos(42, "Refusal Response Rate", Familia.INDICATORS, "refusal_response_rate",
                nota="recusa pode ser o comportamento correto diante de risco"),
    OutputArgos(43, "Vague Response Rate", Familia.INDICATORS, "vague_response_rate"),
    OutputArgos(44, "Rephrase Request Rate", Familia.INDICATORS, "rephrase_request_rate"),
    OutputArgos(45, "Conversation Loop Rate", Familia.INDICATORS, "conversation_loop_rate"),
    OutputArgos(46, "Response Quality Eligible Count", Familia.INDICATORS,
                "response_quality_eligible_count",
                nota="denominador observado dos detectores determinísticos"),
)

CATALOGO: tuple[OutputArgos, ...] = _CATALOGO

POR_ID: Mapping[str, OutputArgos] = MappingProxyType({o.public_id: o for o in _CATALOGO})


def da_familia(familia: str) -> tuple[OutputArgos, ...]:
    """Os outputs de uma família, na ordem do catálogo."""
    return tuple(o for o in _CATALOGO if o.familia == familia)


def publicaveis() -> tuple[OutputArgos, ...]:
    """Tudo que o produto autoriza publicar — o complemento exato dos bloqueados."""
    return tuple(o for o in _CATALOGO if o.familia != Familia.BLOCKED)


def bloqueados() -> tuple[OutputArgos, ...]:
    """Ausências DECLARADAS, com motivo. Nunca publicadas como `not_measured`.

    A distinção importa: `not_measured` diz *"tentamos medir e não deu"*. Um output
    bloqueado nem foi tentado — o produto decidiu não publicá-lo. Emiti-lo como
    `not_measured` seria mentir sobre a natureza da ausência.
    """
    return tuple(o for o in _CATALOGO if o.familia == Familia.BLOCKED)
