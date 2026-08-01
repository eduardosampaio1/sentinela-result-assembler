"""`analysis-facts-v1` — contrato de ENTRADA (interno).

Representa fatos que o domínio analítico **já calculou**. O assembler lê isto; nunca
produz um número que não esteja aqui.

Por que estes nomes: o discovery encontrou em `sentinela @ e7d0703` um contrato de
medição maduro (`core/contracts/measurement.py`) que já separa disponibilidade de valor,
com CINCO estados e motivo tipado. Este arquivo **espelha** aquele vocabulário em vez de
inventar outro — o perfil provisório da E5 tinha só três estados (`available`,
`not_measured`, `not_applicable`) e não sabia expressar "medido sobre subconjunto" nem
"tentou e falhou".

Tudo é `extra="forbid"`: campo não contratado é `schema_mismatch`, não é ignorado em
silêncio. Tudo é `frozen`: os fatos entram e não são mutados durante a montagem.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FactsModel(BaseModel):
    """Base estrita: proíbe campo extra e congela a instância."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _exigir_numero(v: Any) -> Any:
    """Rejeita tudo que não seja `int`/`float` ANTES da coerção do pydantic.

    Dois motivos, os dois encontrados por teste de propriedade e não por inspeção:

    - `True` viraria `1.0`, e aí `isinstance(1.0, bool)` já é False — bool passaria como
      medição válida;
    - `"0"` viraria `0.0`, e aí um produtor que serializa números como texto publicaria
      "zero medido" sem que ninguém tivesse medido zero.

    Coerção é conveniência de entrada de usuário. Aqui a entrada é outra máquina: tipo
    errado significa que o produtor está errado, e isso precisa aparecer.
    """
    if v is not None and (isinstance(v, bool) or not isinstance(v, int | float)):
        raise ValueError(f"esperado número (int/float), recebido {type(v).__name__}")
    return v


class Availability(str, Enum):
    """Estado da medição — NUNCA derivado do valor.

    Espelha `core/contracts/measurement.py::Availability` do domínio.
    """

    AVAILABLE = "available"          # medido; valor confiável (ZERO REAL entra aqui)
    PARTIAL = "partial"              # medido sobre subconjunto DECLARADO
    UNAVAILABLE = "unavailable"      # dado de entrada ausente ou insuficiente
    NOT_EVALUABLE = "not_evaluable"  # os dados existem, a métrica não se aplica
    FAILED = "failed"                # houve tentativa e erro explícito


class Reason(str, Enum):
    """Motivo tipado, para máquina. Espelha `MeasurementReason` do domínio."""

    OK = "ok"
    NO_INPUT_DATA = "no_input_data"
    INSUFFICIENT_SAMPLE = "insufficient_sample"
    SINGLE_GROUP = "single_group"
    MISSING_DIMENSION = "missing_dimension"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    NOT_APPLICABLE = "not_applicable"
    COMPUTATION_ERROR = "computation_error"


class IndicatorKind(str, Enum):
    """Natureza do valor. Decide a formatação PERMITIDA — e nada além dela.

    `ratio` é a única autorização para virar percentual na apresentação. A conversão em
    si NÃO acontece aqui nem no assembler: pertence ao frontend.
    """

    RATIO = "ratio"        # fração 0..1 declarada pela origem
    COUNT = "count"        # contagem absoluta — nunca percentual
    CURRENCY = "currency"  # valor monetário
    SCALAR = "scalar"      # número sem unidade semântica (ex.: variância)


class Denominator(FactsModel):
    """Sobre o QUE a razão foi calculada. Sem isto, `ratio` é um número solto.

    O discovery achou o custo de não ter isto: `outcome_coverage` (cobertura de campo
    `outcome`) e `intent_coverage_rate` (intenções cobertas) são ambos "coverage 0.85" na
    superfície, e significam coisas diferentes.
    """

    kind: str = Field(min_length=1)  # ex.: "records", "intents", "sessions"
    #: `gt=0` no FIELD, não em validador: assim a restrição atravessa para o JSON Schema
    #: publicado (Codex R2 [2]). Um schema mais permissivo que o modelo é pior que schema
    #: nenhum — o produtor valida contra ele, passa, e só descobre na biblioteca.
    value: float = Field(gt=0)

    @field_validator("value", mode="before")
    @classmethod
    def _so_numero(cls, v: Any) -> Any:
        return _exigir_numero(v)

    @field_validator("value")
    @classmethod
    def _finito(cls, v: float) -> float:
        # JSON não tem NaN/Infinity, mas a entrada em Python pode ter.
        if not math.isfinite(float(v)):
            raise ValueError("denominador precisa ser finito")
        return float(v)


class FactIndicator(FactsModel):
    """Um indicador já calculado pelo domínio."""

    id: str = Field(min_length=1)
    kind: IndicatorKind
    availability: Availability
    reason: Reason = Reason.OK

    #: `None` sempre que não houver medição. NUNCA 0 para representar ausência.
    value: float | None = None
    unit: str | None = None
    currency: str | None = None
    denominator: Denominator | None = None

    #: Fração da entrada efetivamente medida (obrigatória em `partial`). A faixa fica no
    #: FIELD para o JSON Schema publicado carregá-la (Codex R2 [3]).
    data_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    observed_units: int | None = Field(default=None, ge=0)
    expected_units: int | None = Field(default=None, gt=0)

    #: Versão do CÁLCULO que produziu este valor — não a do contrato nem a do assembler.
    calculation_version: str = Field(min_length=1)
    #: Origem observável: qual função/módulo do domínio produziu.
    source: str = Field(min_length=1)

    @field_validator("value", "data_coverage", mode="before")
    @classmethod
    def _so_numero(cls, v: Any) -> Any:
        return _exigir_numero(v)

    @field_validator("value")
    @classmethod
    def _valor_finito(cls, v: float | None) -> float | None:
        if v is None:
            return None
        if not math.isfinite(float(v)):
            raise ValueError("value precisa ser finito")
        return float(v)

    @field_validator("data_coverage")
    @classmethod
    def _cobertura_finita(cls, v: float | None) -> float | None:
        # A faixa está no Field (e portanto no schema); aqui sobra só o que JSON não
        # consegue expressar.
        if v is not None and not math.isfinite(float(v)):
            raise ValueError("data_coverage precisa ser finito")
        return None if v is None else float(v)


class FactDimension(FactsModel):
    """Uma dimensão analítica (ex.: `semantic`, `economic`) já composta pelo domínio."""

    id: str = Field(min_length=1)
    availability: Availability
    reason: Reason = Reason.OK
    #: Dimensão é composto normalizado 0..1 no domínio (`aggregate_health`).
    value: float | None = Field(default=None, ge=0.0, le=1.0)
    data_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    calculation_version: str = Field(min_length=1)
    source: str = Field(min_length=1)

    @field_validator("value", "data_coverage", mode="before")
    @classmethod
    def _so_numero(cls, v: Any) -> Any:
        return _exigir_numero(v)

    @field_validator("value")
    @classmethod
    def _valor_finito(cls, v: float | None) -> float | None:
        if v is not None and not math.isfinite(float(v)):
            raise ValueError("value precisa ser finito")
        return None if v is None else float(v)


class FactRecommendation(FactsModel):
    """Recomendação JÁ priorizada e ordenada pelo domínio.

    O discovery confirmou que `engine/recommendations/recommendation_ranker.py` já produz
    `priority` (P1..P4) e `priority_score`, e que `output_consolidator` já ordena. O
    assembler transporta — não escolhe a principal, não reordena por impacto inventado.
    """

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    #: Prioridade declarada pelo domínio. Obrigatória: sem ela não há como transportar
    #: ordem sem inventar.
    priority: str = Field(min_length=1)
    #: Posição explícita na ordem do domínio (0-based, sem repetição).
    order: int = Field(ge=0)
    category: str | None = None
    #: Ids de evidência relacionados (precisam existir na seção de evidências).
    evidence_refs: tuple[str, ...] = ()


class FactEvidenceSummary(FactsModel):
    """Resumo de evidência — agregado e seguro por construção.

    Não carrega texto livre de conversa, prompt, resposta, caminho, chave nem id interno.
    O que passa é declarado campo a campo aqui; a validação de segurança confere de novo.
    """

    id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    #: Quantos itens sustentam a evidência. Agregado, nunca o conteúdo.
    observed_count: int = Field(ge=0)
    #: Rótulo curto e já sanitizado pelo domínio (ex.: nome de intenção).
    label: str | None = None


class FactsIdentity(FactsModel):
    """Identidade da análise. `analysis_id` é o único id que atravessa para o público."""

    analysis_id: str = Field(min_length=1)
    #: Ids internos — ficam no manifesto, nunca no resultado público.
    job_id: str | None = None
    analysis_run_id: str | None = None


class AnalysisWindow(FactsModel):
    """Quando e sobre quanto a análise foi feita. Datas vêm como FATO.

    `analyzed_at` é obrigatório: o assembler não tem relógio. Fabricar a data aqui seria
    a mentira mais barata de detectar e a mais cara de descobrir em produção.
    """

    analyzed_at: str = Field(min_length=1)  # ISO-8601, produzido pelo domínio
    record_count: int = Field(ge=0)


class CalculationProvenance(FactsModel):
    """De onde os números vieram. Vai para o manifesto interno; não para o público."""

    engine_version: str = Field(min_length=1)
    analysis_version: str | None = None
    dataset_fingerprint: str | None = None


class AnalysisFacts(FactsModel):
    """Envelope de entrada `analysis-facts-v1`."""

    facts_schema_version: str = Field(min_length=1)
    measurement_contract_version: str = Field(min_length=1)
    identity: FactsIdentity
    window: AnalysisWindow
    provenance: CalculationProvenance
    indicators: tuple[FactIndicator, ...] = ()
    dimensions: tuple[FactDimension, ...] = ()
    recommendations: tuple[FactRecommendation, ...] = ()
    evidence: tuple[FactEvidenceSummary, ...] = ()
