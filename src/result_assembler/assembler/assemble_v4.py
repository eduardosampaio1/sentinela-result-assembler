"""Montagem allowlist do resultado v4; nenhum número é calculado aqui."""

from __future__ import annotations

from dataclasses import dataclass

from result_assembler.assembler.assemble_v3 import assemble_v3
from result_assembler.contracts.facts import AnalysisFactsV3, AnalysisFactsV4
from result_assembler.contracts.result_v4 import PublicResultV4
from result_assembler.version import FACTS_SCHEMA_V3_VERSION, RESULT_SCHEMA_V4_VERSION


@dataclass(frozen=True)
class AssemblyV4Outcome:
    public_result: PublicResultV4


def assemble_v4(facts: AnalysisFactsV4) -> AssemblyV4Outcome:
    base = facts.model_dump(mode="python", exclude={"workload_profile", "economics_assessment"})
    base["facts_schema_version"] = FACTS_SCHEMA_V3_VERSION
    public_v3 = assemble_v3(AnalysisFactsV3.model_validate(base)).public_result
    payload = public_v3.model_dump(mode="python")
    payload["result_schema_version"] = RESULT_SCHEMA_V4_VERSION
    payload["workload_profile"] = facts.workload_profile.model_dump(mode="python")
    payload["economics_assessment"] = facts.economics_assessment.model_dump(mode="python")
    return AssemblyV4Outcome(public_result=PublicResultV4.model_validate(payload))
