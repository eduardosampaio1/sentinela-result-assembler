from __future__ import annotations

from result_assembler import AnalysisFactsV4, assemble_v4, parse_facts


def payload() -> dict:
    def measured(value: int | None, level: str = "observed") -> dict:
        return {"value": value, "truth_level": level, "method": "test", "assumptions": []}

    current_model = {
        "status": "unknown", "provider": None, "model_id": None,
        "pricing_route": None, "coverage": 0.0,
    }
    comparison = {
        "status": "estimated", "reason": "workload_contains_estimates",
        "route_id": "p:m", "provider": "p", "model_id": "m",
        "currency": "USD", "total_cost": 1.25, "line_items": [],
        "normalized_costs": {"per_1k": 1.25, "per_100k": 125.0, "per_1m": 1250.0},
    }
    return {
        "facts_schema_version": "analysis-facts-v4",
        "measurement_contract_version": "measurement-1.0",
        "identity": {"analysis_id": "a-1", "job_id": "a-1", "analysis_run_id": None},
        "window": {"analyzed_at": "2026-08-30T00:00:00Z", "record_count": 1},
        "provenance": {
            "engine_version": "test",
            "analysis_version": "1",
            "dataset_fingerprint": "f",
        },
        "indicators": [], "dimensions": [], "recommendations": [], "evidence": [],
        "alerts": None, "issues": None, "executive_summary": None,
        "scores": None, "risks": None, "projections": None, "intents": None, "method": None,
        "workload_profile": {
            "schema_version": "workload-profile-v1",
            "population": {
                "analysis_records": measured(1),
                "conversation_count": measured(None, "unknown"),
                "message_count": measured(None, "unknown"),
            },
            "tokens": {
                "raw_dataset_input_tokens": measured(10, "derived"),
                "raw_dataset_output_tokens": measured(20, "derived"),
                "effective_inference_input_tokens": measured(None, "unknown"),
                "observed_output_tokens": measured(None, "unknown"),
                "cache_read_tokens": measured(None, "unknown"),
                "cache_write_tokens": measured(None, "unknown"),
                "reasoning_tokens": measured(None, "unknown"),
                "embedding_tokens": measured(20, "derived"),
            },
            "context_distribution": {
                "unit": "derived_tokens_per_analysis_record", "average": 30.0,
                "p50": 30, "p75": 30, "p95": 30, "p99": 30,
            },
            "history_scenarios": {
                "stateless_input_tokens": measured(10, "derived"),
                "full_replay_input_tokens": measured(None, "unknown"),
            },
            "embedding_workload": {
                "texts_embedded": measured(1), "model": "test", "dimension": 384,
                "reused_from_cache": measured(None, "unknown"),
            },
            "current_model": current_model,
            "billing_semantics": {
                "input_token_cache_accounting": measured(None, "unknown")
            },
            "limitations": ["test limitation"],
        },
        "economics_assessment": {
            "schema_version": "economics-assessment-v1", "availability": "available",
            "reason": "ok", "registry": None, "current_model": current_model,
            "comparisons": [comparison], "inference_comparisons": [comparison],
            "embedding_comparisons": [], "unsupported_routes": 0,
            "disclaimer": "cost is not quality",
        },
    }


def test_v4_transporta_sem_recalcular() -> None:
    facts = parse_facts(payload())
    assert isinstance(facts, AnalysisFactsV4)
    result = assemble_v4(facts).public_result.model_dump(mode="json")
    assert result["result_schema_version"] == "analysis-result-v4"
    assert result["economics_assessment"]["comparisons"][0]["total_cost"] == 1.25
    assert result["workload_profile"]["population"]["analysis_records"]["value"] == 1


def test_v4_recusa_documento_finops_sem_versao() -> None:
    bad = payload()
    bad["workload_profile"] = {"population": {}}
    try:
        parse_facts(bad)
    except Exception as exc:
        assert getattr(exc, "category", "") == "schema_mismatch"
    else:  # pragma: no cover
        raise AssertionError("versão ausente deveria ser recusada")


def test_v4_recusa_campo_economico_desconhecido() -> None:
    bad = payload()
    bad["economics_assessment"]["comparisons"][0]["magic_saving"] = 99
    try:
        parse_facts(bad)
    except Exception as exc:
        assert getattr(exc, "category", "") == "schema_mismatch"
    else:  # pragma: no cover
        raise AssertionError("campo econômico desconhecido deveria ser recusado")
