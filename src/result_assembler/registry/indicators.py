"""Registro canônico de indicadores públicos.

O registro **não calcula nada**. Ele responde a uma pergunta só: *este fato pode virar
este indicador público, com esta unidade, este denominador e esta faixa?* — e recusa
quando não pode.

Critério de entrada (o mais importante deste arquivo): só entra fato cuja fórmula o
discovery leu **no código do produtor** e cujo significado é inequívoco. Ficaram DE FORA,
com motivo, coisas que hoje existem no pipeline mas não são fatos honestos:

- `handoff_rate` — o produtor calcula `1 - useful_rate`
  (`engine/business/unit_economics.py`). Com ZERO handoffs medidos ele devolve 0.2 num
  dataset de `useful_rate=0.8`. Não é taxa de handoff; é o complemento de outra métrica.
  Publicar isso com esse nome seria contratar um erro.
- `token_waste_estimate` e derivados — a origem é `int(round(avg_tokens))`, anotada com
  `# proxy` no próprio `core/sentinela_engine.py`. Um proxy pode ser útil internamente;
  como indicador público contratado, não.
- `confidence` / composto de saúde — existem e são honestos no domínio, mas dependem do
  composto `Measurement` (F2.5) que ainda não chega até aqui como fato. Entram quando o
  produtor os emitir como `analysis-facts-v1`.

`display_precision` é **sugestão de apresentação**. O assembler não arredonda o valor: o
sub-centavo `0.0042` precisa chegar íntegro ao consumidor, que decide como mostrar.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from result_assembler.contracts.facts import Availability, IndicatorKind

#: Versão do registro. Muda quando um indicador entra, sai ou muda de semântica.
INDICATOR_REGISTRY_VERSION = "indicator-registry-1.0"

#: Versões de cálculo aceitas nesta release. Hoje há uma só; a exigência de que o
#: produtor DECLARE a versão é o ponto — sem ela não há como recusar um número velho.
_V1 = frozenset({"1.0"})

_ECONOMICS = "engine.business.cost_estimators.estimate_useful_outcome_economics"
_TENANT = "engine.business.unit_economics.compute_tenant_metrics"

#: Estados possíveis para um indicador que pode simplesmente não ter sido medido.
_QUALQUER_ESTADO = frozenset(
    {
        Availability.AVAILABLE,
        Availability.PARTIAL,
        Availability.UNAVAILABLE,
        Availability.NOT_EVALUABLE,
        Availability.FAILED,
    }
)


@dataclass(frozen=True)
class IndicatorDefinition:
    """Contrato de UM indicador público."""

    public_id: str
    description: str
    kind: IndicatorKind
    unit: str | None
    #: `kind` do denominador exigido. `None` = indicador não precisa de denominador.
    denominator_kind: str | None
    #: Faixa válida INCLUSIVA do valor. `None` = sem faixa contratada.
    valid_range: tuple[float, float] | None
    display_precision: int
    allowed_availability: frozenset[Availability]
    accepted_calculation_versions: frozenset[str]
    accepted_sources: frozenset[str]


def _razao(
    public_id: str, description: str, denom: str, source: str, precision: int = 4
) -> IndicatorDefinition:
    return IndicatorDefinition(
        public_id=public_id,
        description=description,
        kind=IndicatorKind.RATIO,
        unit="ratio",
        denominator_kind=denom,
        valid_range=(0.0, 1.0),
        display_precision=precision,
        allowed_availability=_QUALQUER_ESTADO,
        accepted_calculation_versions=_V1,
        accepted_sources=frozenset({source}),
    )


def _contagem(
    public_id: str, description: str, source: str, unit: str = "records"
) -> IndicatorDefinition:
    return IndicatorDefinition(
        public_id=public_id,
        description=description,
        kind=IndicatorKind.COUNT,
        unit=unit,
        denominator_kind=None,
        valid_range=(0.0, float("inf")),  # contagem negativa é proibida
        display_precision=0,
        allowed_availability=_QUALQUER_ESTADO,
        accepted_calculation_versions=_V1,
        accepted_sources=frozenset({source}),
    )


def _moeda(
    public_id: str,
    description: str,
    source: str,
    denom: str | None = None,
    precision: int = 6,
) -> IndicatorDefinition:
    return IndicatorDefinition(
        public_id=public_id,
        description=description,
        kind=IndicatorKind.CURRENCY,
        unit="currency",
        denominator_kind=denom,
        valid_range=(0.0, float("inf")),
        display_precision=precision,
        allowed_availability=_QUALQUER_ESTADO,
        accepted_calculation_versions=_V1,
        accepted_sources=frozenset({source}),
    )


_DEFINICOES: dict[str, IndicatorDefinition] = {
    # ── razões (0..1) ────────────────────────────────────────────────────────────
    "useful_rate": _razao(
        "useful_outcome_rate",
        "Fração das conversas analisadas com desfecho útil, conforme o domínio.",
        "analyzed_conversations",
        _ECONOMICS,
    ),
    # Nome público EXPLÍCITO: o produtor chama de `outcome_coverage`, mas o que ele mede
    # é a presença do campo `outcome` — não cobertura de intenções. Publicar como
    # "coverage" seco foi exatamente a ambiguidade que a E5 herdou.
    "outcome_coverage": _razao(
        "outcome_field_coverage_rate",
        "Fração das conversas em que o campo de desfecho estava presente. NÃO é cobertura "
        "de intenções.",
        "analyzed_conversations",
        _ECONOMICS,
    ),
    "conversion_rate": _razao(
        "conversion_rate",
        "Fração das conversas analisadas marcadas como conversão.",
        "analyzed_conversations",
        _ECONOMICS,
    ),
    "intent_coverage_rate": _razao(
        "intent_coverage_rate",
        "Fração das intenções do catálogo efetivamente cobertas pelo dataset.",
        "intents",
        _TENANT,
    ),
    # ── contagens (nunca percentual) ─────────────────────────────────────────────
    "observed_conversations": _contagem(
        "analyzed_conversation_count",
        "Quantidade de conversas que a análise considerou.",
        _ECONOMICS,
        unit="conversations",
    ),
    "useful_outcomes": _contagem(
        "useful_outcome_count",
        "Quantidade de conversas com desfecho útil.",
        _ECONOMICS,
        unit="conversations",
    ),
    "actual_handoffs": _contagem(
        "handoff_count",
        "Quantidade de conversas que resultaram em handoff humano — MEDIDA, não derivada "
        "de outra taxa.",
        _ECONOMICS,
        unit="conversations",
    ),
    "conversion_count": _contagem(
        "conversion_count",
        "Quantidade de conversas marcadas como conversão.",
        _ECONOMICS,
        unit="conversations",
    ),
    # ── moeda ────────────────────────────────────────────────────────────────────
    "total_estimated_cost": _moeda(
        "total_estimated_cost",
        "Custo total estimado da operação analisada (tokens + handoffs).",
        _ECONOMICS,
    ),
    "observed_token_cost_total": _moeda(
        "token_cost_total",
        "Parcela do custo total atribuída a tokens.",
        _ECONOMICS,
    ),
    "observed_handoff_cost_total": _moeda(
        "handoff_cost_total",
        "Parcela do custo total atribuída a handoffs.",
        _ECONOMICS,
    ),
    # Sem desfecho útil, o produtor devolve `None` — e é assim que precisa chegar ao
    # público. O adapter legado (`core/adapters/argos.py`) colapsa isso em 0.0; aqui
    # `not_measured` com `value=null` é o desfecho correto.
    "cost_per_useful_outcome": _moeda(
        "cost_per_useful_outcome",
        "Custo total dividido pelos desfechos úteis. Indisponível quando não houve "
        "desfecho útil.",
        _ECONOMICS,
        denom="useful_outcomes",
    ),
    "cost_per_session": _moeda(
        "cost_per_session",
        "Custo total dividido pelas conversas analisadas.",
        _TENANT,
        denom="analyzed_conversations",
    ),
    # ── escalar ──────────────────────────────────────────────────────────────────
    # É VARIÂNCIA. Não é consistência, não é estabilidade, não é confiança e não é drift
    # — o nome público diz o que é para que ninguém precise adivinhar.
    "avg_variance_per_intent": IndicatorDefinition(
        public_id="mean_response_variance_per_intent",
        description="Média da variância de resposta entre intenções. Variância — valor "
        "maior significa MAIS dispersão, não mais qualidade.",
        kind=IndicatorKind.SCALAR,
        unit=None,
        denominator_kind=None,
        valid_range=(0.0, float("inf")),
        display_precision=4,
        allowed_availability=_QUALQUER_ESTADO,
        accepted_calculation_versions=_V1,
        accepted_sources=frozenset({_TENANT}),
    ),
}

#: Só leitura: ninguém registra indicador em tempo de execução.
INDICATOR_REGISTRY: Mapping[str, IndicatorDefinition] = MappingProxyType(_DEFINICOES)

#: Ordem canônica de publicação. Determinismo vem DAQUI, não da ordem em que os fatos
#: chegaram: dois produtores com a mesma medição precisam gerar os mesmos bytes.
CANONICAL_ORDER: tuple[str, ...] = (
    "useful_rate",
    "outcome_coverage",
    "conversion_rate",
    "intent_coverage_rate",
    "observed_conversations",
    "useful_outcomes",
    "actual_handoffs",
    "conversion_count",
    "total_estimated_cost",
    "observed_token_cost_total",
    "observed_handoff_cost_total",
    "cost_per_useful_outcome",
    "cost_per_session",
    "avg_variance_per_intent",
)

#: Dimensões analíticas publicáveis. São as QUATRO do composto de saúde (F2.5) lidas em
#: `core/_engine_helpers.py` — `_DIMENSOES_AI_HEALTH`. Fail-closed pelo mesmo motivo dos
#: indicadores: dimensão nova precisa de decisão humana, não de passagem automática.
SUPPORTED_DIMENSION_IDS: frozenset[str] = frozenset(
    {"semantic", "behavioral", "structural", "economic"}
)


def definicao_de(internal_id: str) -> IndicatorDefinition | None:
    """Definição pública do fato, ou `None` se ele não é um indicador contratado."""
    return INDICATOR_REGISTRY.get(internal_id)
