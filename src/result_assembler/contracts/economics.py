"""Contratos estritos para o perfil de workload e o Economics oficiais."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EconomicsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MeasuredValue(EconomicsModel):
    value: int | float | str | None
    truth_level: Literal["observed", "derived", "estimated", "unknown"]
    method: str = Field(min_length=1)
    assumptions: tuple[str, ...] = ()
    coverage: float | None = Field(default=None, ge=0.0, le=1.0)


class WorkloadPopulation(EconomicsModel):
    analysis_records: MeasuredValue
    conversation_count: MeasuredValue
    message_count: MeasuredValue


class WorkloadTokens(EconomicsModel):
    raw_dataset_input_tokens: MeasuredValue
    raw_dataset_output_tokens: MeasuredValue
    effective_inference_input_tokens: MeasuredValue
    observed_output_tokens: MeasuredValue
    cache_read_tokens: MeasuredValue
    cache_write_tokens: MeasuredValue
    reasoning_tokens: MeasuredValue
    embedding_tokens: MeasuredValue


class ContextDistribution(EconomicsModel):
    unit: str = Field(min_length=1)
    average: float | None
    p50: int | None
    p75: int | None
    p95: int | None
    p99: int | None


class HistoryScenarios(EconomicsModel):
    stateless_input_tokens: MeasuredValue
    full_replay_input_tokens: MeasuredValue


class EmbeddingWorkload(EconomicsModel):
    texts_embedded: MeasuredValue
    model: str | None
    dimension: int | None = Field(default=None, gt=0)
    reused_from_cache: MeasuredValue


class CurrentModel(EconomicsModel):
    status: Literal["detected", "declared", "inferred", "unknown"]
    provider: str | None
    model_id: str | None
    pricing_route: str | None
    coverage: float = Field(ge=0.0, le=1.0)
    sample_size: int | None = Field(default=None, ge=0)
    reason: str | None = None


class BillingSemantics(EconomicsModel):
    input_token_cache_accounting: MeasuredValue


class WorkloadProfile(EconomicsModel):
    schema_version: Literal["workload-profile-v1"]
    population: WorkloadPopulation
    tokens: WorkloadTokens
    context_distribution: ContextDistribution
    history_scenarios: HistoryScenarios
    embedding_workload: EmbeddingWorkload
    current_model: CurrentModel
    billing_semantics: BillingSemantics
    limitations: tuple[str, ...]


class PricingRegistryRef(EconomicsModel):
    schema_version: str | None
    capture_id: str | None
    captured_at: str | None
    content_digest_sha256: str | None
    primary_source: str | None
    validation_sources: tuple[str, ...] = ()


class CostLineItem(EconomicsModel):
    kind: str = Field(min_length=1)
    tokens: int = Field(ge=0)
    truth_level: Literal["observed", "derived", "estimated", "unknown"]
    price_per_million: float = Field(ge=0.0)
    amount: float = Field(ge=0.0)


class NormalizedCosts(EconomicsModel):
    per_1k: float | None
    per_100k: float | None
    per_1m: float | None


class CostComparison(EconomicsModel):
    status: Literal[
        "exact", "estimated", "not_enough_information", "unsupported_pricing_rule"
    ]
    reason: str = Field(min_length=1)
    route_id: str | None
    provider: str | None
    hosting_provider: str | None = None
    model_id: str | None
    model_family: str | None = None
    pricing_tier: str | None = None
    route_kind: str | None = None
    currency: str = Field(min_length=1)
    total_cost: float | None = Field(default=None, ge=0.0)
    line_items: tuple[CostLineItem, ...] = ()
    pricing_source: str | None = None
    pricing_source_url: str | None = None
    price_captured_at: str | None = None
    price_effective_at: str | None = None
    calculation_version: str | None = None
    normalized_costs: NormalizedCosts | None = None
    unknown_priced_dimensions: tuple[str, ...] = ()


class EconomicsAssessment(EconomicsModel):
    schema_version: Literal["economics-assessment-v1"]
    availability: Literal["available", "unavailable"]
    reason: str = Field(min_length=1)
    detail_code: str | None = None
    registry: PricingRegistryRef | None
    current_model: CurrentModel | None = None
    current_model_comparison: CostComparison | None = None
    comparisons: tuple[CostComparison, ...]
    inference_comparisons: tuple[CostComparison, ...] = ()
    embedding_comparisons: tuple[CostComparison, ...] = ()
    unsupported_routes: int = Field(default=0, ge=0)
    disclaimer: str | None = None
