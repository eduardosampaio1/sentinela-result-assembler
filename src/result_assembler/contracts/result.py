"""`analysis-result-v1` — contrato de SAÍDA (público).

Consumido por Result Store → Gateway → frontend. É um modelo **diferente** do de entrada,
de propósito: se fosse o mesmo, todo campo interno novo no domínio vazaria para o público
por omissão. Aqui o vazamento exige alguém escrever o campo.

O que este contrato garante ao consumidor:

- **zero real é distinguível de ausência** — `state="measured"` com `value=0.0` não é a
  mesma coisa que `state="not_measured"` com `value=null`;
- **cada ausência tem nome** — não medido, não aplicável, falhou no cálculo e parcial são
  estados distintos, não todos `null`;
- **razão declara o denominador** — `useful_rate=0.8` sem "sobre 100 registros" é um
  número que o consumidor não pode auditar;
- **nada de identidade interna** — sem job_id, sem worker, sem engine, sem chave de
  objeto, sem caminho.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ResultModel(BaseModel):
    """Base estrita do lado público."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class IndicatorState(str, Enum):
    """O que o consumidor precisa saber ANTES de olhar o valor.

    Mapeado 1-para-1 a partir da disponibilidade dos fatos; nunca inferido do valor.
    """

    #: Medido, valor confiável. **Zero real mora aqui** (`value=0.0`).
    MEASURED = "measured"
    #: Medido sobre subconjunto declarado — `coverage` diz quanto.
    PARTIALLY_MEASURED = "partially_measured"
    #: Não foi medido nesta análise (entrada ausente ou amostra insuficiente).
    NOT_MEASURED = "not_measured"
    #: Os dados existem, a métrica não se aplica.
    NOT_APPLICABLE = "not_applicable"
    #: Houve tentativa e erro explícito no cálculo.
    CALCULATION_FAILED = "calculation_failed"


class PublicDenominator(ResultModel):
    """Sobre o que a razão foi calculada — publicado para permitir auditoria."""

    kind: str
    value: float


class PublicIndicator(ResultModel):
    """Um indicador no resultado público."""

    id: str
    state: IndicatorState
    #: `null` em toda ausência. Presente (podendo ser 0.0) quando medido.
    value: float | None
    kind: str
    unit: str | None
    currency: str | None
    denominator: PublicDenominator | None
    #: Só em `partially_measured`; declara a fração medida.
    coverage: float | None
    #: Precisão RECOMENDADA para exibição, vinda do registro. É sugestão de apresentação,
    #: não arredondamento aplicado ao valor — o valor sai como o domínio calculou.
    display_precision: int


class PublicDimension(ResultModel):
    """Uma dimensão analítica no resultado público."""

    id: str
    state: IndicatorState
    value: float | None
    coverage: float | None


class PublicRecommendation(ResultModel):
    """Recomendação transportada na ordem e prioridade do domínio."""

    id: str
    title: str
    priority: str
    category: str | None
    evidence_refs: tuple[str, ...]


class PublicEvidenceSummary(ResultModel):
    """Resumo agregado de evidência — só campos da allowlist."""

    id: str
    kind: str
    observed_count: int
    label: str | None


class PublicSummary(ResultModel):
    """Cabeçalho legível da análise."""

    #: Quantos registros a análise considerou (fato do domínio).
    record_count: int
    #: Produzido pelo domínio. O assembler não tem relógio.
    analyzed_at: str


class Partiality(ResultModel):
    """Declara explicitamente se o resultado é completo — em vez de deixar o consumidor
    inferir pela ausência.

    Não existe lista de "indicadores excluídos" porque a montagem é **fail-closed**: um
    indicador desconhecido ou uma versão incompatível recusam a montagem inteira, não são
    omitidos em silêncio. Logo, todo indicador que os fatos trouxeram está aqui — o que
    varia é o ESTADO de cada um, e é isso que `reasons` resume.
    """

    #: `True` só quando todo indicador publicado está `measured`.
    complete: bool
    #: Motivos ordenados e sem repetição que impedem `complete` (vazio quando completo).
    reasons: tuple[str, ...]


class PublicResult(ResultModel):
    """Envelope público `analysis-result-v1`."""

    analysis_id: str
    result_schema_version: str
    #: Versão da SEMÂNTICA de medição sob a qual estes números valem. Publicada porque
    #: comparar dois resultados de contratos diferentes é um erro que só o consumidor
    #: pode evitar — e só consegue se souber.
    measurement_contract_version: str
    summary: PublicSummary
    indicators: tuple[PublicIndicator, ...] = Field(default=())
    dimensions: tuple[PublicDimension, ...] = Field(default=())
    recommendations: tuple[PublicRecommendation, ...] = Field(default=())
    evidence: tuple[PublicEvidenceSummary, ...] = Field(default=())
    partiality: Partiality
