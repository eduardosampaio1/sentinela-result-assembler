from copy import deepcopy

import pytest

from result_assembler import parse_facts
from result_assembler.validation.invariants import validate_facts
from result_assembler.errors import InvalidDenominator


def _facts(version: str, denominator_kind: str) -> dict:
    return {
        "facts_schema_version": "analysis-facts-v1",
        "measurement_contract_version": "measurement-1.0",
        "identity": {
            "analysis_id": "analysis-outcome",
            "job_id": "job-outcome",
            "analysis_run_id": "run-outcome",
        },
        "window": {"analyzed_at": "2026-09-01T00:00:00Z", "record_count": 10},
        "provenance": {
            "engine_version": "test",
            "analysis_version": "deep",
            "dataset_fingerprint": "sha256:test-outcome",
        },
        "indicators": [
            {
                "id": "useful_rate",
                "kind": "ratio",
                "availability": "available",
                "reason": "ok",
                "value": 0.75,
                "unit": "ratio",
                "denominator": {"kind": denominator_kind, "value": 8},
                "calculation_version": version,
                "source": "engine.business.cost_estimators.estimate_useful_outcome_economics",
            }
        ],
    }


def test_legacy_outcome_rate_keeps_legacy_denominator() -> None:
    validate_facts(parse_facts(_facts("1.0", "analyzed_conversations")))


def test_canonical_outcome_rate_uses_only_interpretable_outcomes() -> None:
    validate_facts(parse_facts(_facts("1.1", "interpretable_outcomes")))


def test_canonical_version_rejects_legacy_denominator() -> None:
    payload = deepcopy(_facts("1.1", "analyzed_conversations"))
    with pytest.raises(InvalidDenominator):
        validate_facts(parse_facts(payload))
