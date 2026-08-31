"""`analysis-result-v4`: v3 + workload e Economics oficiais."""

from __future__ import annotations

from result_assembler.contracts.economics import EconomicsAssessment, WorkloadProfile
from result_assembler.contracts.result_v3 import (
    PublicAlert,  # noqa: F401 -- resolve forward refs herdadas
    PublicExecutiveSummary,  # noqa: F401
    PublicIndicatorV3,  # noqa: F401
    PublicIssue,  # noqa: F401
    PublicResultV3,
)
from result_assembler.version import RESULT_SCHEMA_V4_VERSION


class PublicResultV4(PublicResultV3):
    result_schema_version: str = RESULT_SCHEMA_V4_VERSION
    workload_profile: WorkloadProfile
    economics_assessment: EconomicsAssessment


# Resolve os forward refs herdados de PublicResultV3 neste novo módulo.
PublicResultV4.model_rebuild()
