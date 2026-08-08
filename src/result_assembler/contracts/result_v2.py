"""`analysis-result-v2` — o documento INTEGRADO (MF6.2).

    Engine facts  +  Analytics public projection  →  analysis-result-v2

## Por que v2, e não um bloco aditivo no v1

`analysis-result-v1` tem `additionalProperties: false`. Qualquer acréscimo é quebra para quem
valida contra o schema publicado — inclusive um campo opcional. A diferença entre evoluir o v1 e
criar o v2 nunca foi "quebra × não quebra": era **quem** quebra. O v1 permanece exatamente como
está, e quem o consome hoje continua consumindo.

## As duas contagens, e o nome que muda (MF6.3)

O v1 chama de `summary.record_count` a janela que a ENGINE analisou. O lado analítico tem o
próprio denominador, com o mesmo nome e definição diferente. Pôr os dois no mesmo documento sob o
mesmo nome é a divergência silenciosa que esta plataforma existe para não ter.

No v2 a da Engine ganha nome próprio — `engine_window_record_count` — e o denominador analítico
mora no bloco `analytics`. **`summary.record_count` do v1 não se mexe**: ele continua lá, no v1,
significando o que sempre significou.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from result_assembler.contracts.analytics import ComponentStatus
from result_assembler.contracts.result import (
    Partiality,
    PublicDimension,
    PublicEvidenceSummary,
    PublicIndicator,
    PublicRecommendation,
)


class ResultV2Model(BaseModel):
    """Base estrita, igual à do v1: `extra=forbid` e imutável."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class PublicSummaryV2(ResultV2Model):
    """Cabeçalho do documento integrado. **Nenhum campo chamado `record_count`.**

    A ausência é deliberada e é o ponto da MF6.3: com duas contagens no mesmo documento, um nome
    ambíguo faria a errada ser lida. Quem quer a janela da Engine pede
    `engine_window_record_count`; quem quer o denominador analítico pede `analytics.record_count`.
    """

    #: A contagem **A**: a janela que a Engine analisou. Era `summary.record_count` no v1.
    engine_window_record_count: int = Field(ge=0)
    #: Produzido pelo domínio. O assembler não tem relógio.
    analyzed_at: str


class PublicAnalyticsBlock(ResultV2Model):
    """O bloco analítico. **Wrapper obrigatório, conteúdo anulável.**

    Obrigatório porque a ausência do bloco e a decisão de não liberar nada são coisas diferentes,
    e um documento que as confundisse deixaria o consumidor adivinhar. Anulável porque `withheld`
    é conclusão válida.
    """

    component_status: ComponentStatus
    projection_digest: str = Field(min_length=1)
    snapshot_contract_version: str = Field(min_length=1)
    #: O denominador analítico — a contagem **C**. `None` quando `withheld`, porque não há
    #: projeção sobre a qual contar.
    record_count: int | None = Field(default=None, ge=0)
    #: A projeção pública, transportada sem interpretação. `None` quando `withheld`.
    data: dict[str, Any] | None = None


class PublicResultV2(ResultV2Model):
    """O documento integrado. Mesma espinha do v1, mais o bloco analítico e o nome novo."""

    analysis_id: str
    result_schema_version: str
    #: Da ENGINE. O lado analítico tem a própria em `analytics.snapshot_contract_version` — uma
    #: versão não pode descrever duas coisas que evoluem separadas.
    measurement_contract_version: str
    summary: PublicSummaryV2
    indicators: tuple[PublicIndicator, ...] = Field(default=())
    dimensions: tuple[PublicDimension, ...] = Field(default=())
    recommendations: tuple[PublicRecommendation, ...] = Field(default=())
    evidence: tuple[PublicEvidenceSummary, ...] = Field(default=())
    partiality: Partiality
    #: **Obrigatório.** Ver `PublicAnalyticsBlock`.
    analytics: PublicAnalyticsBlock


__all__ = ["PublicAnalyticsBlock", "PublicResultV2", "PublicSummaryV2", "ResultV2Model"]
