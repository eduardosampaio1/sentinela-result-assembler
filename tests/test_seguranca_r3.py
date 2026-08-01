"""Achados da revisão de segurança (Codex R3).

Cada teste usa um segredo reconhecível e prova que ele **não aparece** onde não deve.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from massas import carregar_json
from result_assembler import (
    AssemblyError,
    UnsafeEvidence,
    assemble,
    parse_facts,
    serialize_canonical,
)

SEGREDO = "Bearer sk-live-SEGREDO-QUE-NAO-PODE-VAZAR"


def massa_f() -> dict[str, Any]:
    return carregar_json("massa_f_recomendacoes_evidencias.facts.json")


@pytest.mark.security
class TestIdsTambemSaoVarridos:
    """Codex R3 [1] — `evidence.id`, `recommendation.id` e `evidence_refs` atravessam
    para o público tal como chegaram. Chamar de "id" não os torna seguros."""

    def test_id_de_evidencia_com_credencial_recusa(self):
        bruto = massa_f()
        bruto["evidence"][0]["id"] = SEGREDO
        bruto["recommendations"][2]["evidence_refs"] = []
        for rec in bruto["recommendations"]:
            rec["evidence_refs"] = [r for r in rec["evidence_refs"] if r != "ev-2"]
        with pytest.raises(UnsafeEvidence):
            assemble(parse_facts(bruto))

    def test_id_de_recomendacao_com_credencial_recusa(self):
        bruto = massa_f()
        bruto["recommendations"][0]["id"] = SEGREDO
        with pytest.raises(UnsafeEvidence):
            assemble(parse_facts(bruto))

    def test_evidence_ref_com_caminho_recusa(self):
        bruto = massa_f()
        caminho = "/var/lib/sentinela/jobs/an-1/dataset.jsonl"
        bruto["evidence"].append(
            {"id": caminho, "kind": "grupo", "observed_count": 1, "label": None}
        )
        bruto["recommendations"][0]["evidence_refs"] = [caminho]
        with pytest.raises(UnsafeEvidence):
            assemble(parse_facts(bruto))

    def test_id_normal_continua_passando(self):
        assemble(parse_facts(massa_f()))


@pytest.mark.security
class TestErroNaoEcoaIdDoPayload:
    """Codex R3 [3] — a mensagem ecoava ids controlados pelo payload. Um id duplicado
    valendo um token levaria o token para o log."""

    def _sem_segredo(self, exc: AssemblyError, onde: str) -> None:
        assert SEGREDO not in str(exc)
        assert onde in str(exc)

    def test_recomendacao_duplicada(self):
        bruto = massa_f()
        # Duas recomendações com o MESMO id — que é o segredo.
        for i in (0, 1):
            bruto["recommendations"][i]["id"] = SEGREDO
        with pytest.raises(AssemblyError) as exc:
            assemble(parse_facts(bruto))
        self._sem_segredo(exc.value, "recommendations[")

    def test_indicador_desconhecido(self):
        bruto = carregar_json("massa_a_principal.facts.json")
        bruto["indicators"][0]["id"] = SEGREDO
        with pytest.raises(AssemblyError) as exc:
            assemble(parse_facts(bruto))
        self._sem_segredo(exc.value, "indicators[0]")

    def test_indicador_duplicado(self):
        bruto = carregar_json("massa_a_principal.facts.json")
        bruto["indicators"].append(dict(bruto["indicators"][0]))
        with pytest.raises(AssemblyError) as exc:
            assemble(parse_facts(bruto))
        assert "indicators[11]" in str(exc.value)
        assert "useful_rate" not in str(exc.value)

    def test_dimensao_desconhecida(self):
        bruto = carregar_json("massa_a_principal.facts.json")
        bruto["dimensions"] = [
            {
                "id": SEGREDO,
                "availability": "available",
                "reason": "ok",
                "value": 0.5,
                "data_coverage": None,
                "calculation_version": "1.0",
                "source": "core._engine_helpers.build_ai_health_measurement",
            }
        ]
        with pytest.raises(AssemblyError) as exc:
            assemble(parse_facts(bruto))
        self._sem_segredo(exc.value, "dimensions[0]")

    def test_evidence_ref_orfa(self):
        bruto = massa_f()
        bruto["evidence"].append(
            {"id": "ev-9", "kind": "grupo", "observed_count": 1, "label": None}
        )
        bruto["recommendations"][0]["evidence_refs"] = ["ev-nao-existe"]
        with pytest.raises(AssemblyError) as exc:
            assemble(parse_facts(bruto))
        assert "ev-nao-existe" not in str(exc.value)
        assert "recommendations[" in str(exc.value)


@pytest.mark.security
class TestManifestoEInternoPorDesenho:
    """Codex R3 [2] — a promessa era mais forte que o código.

    O manifesto CARREGA `job_id`/`engine_version`/`dataset_fingerprint` de propósito: é
    disso que proveniência técnica é feita. O que ele não pode carregar é CONTEÚDO
    analítico. A correção foi na promessa (docstring), não no manifesto.
    """

    def test_carrega_identificadores_internos_de_proposito(self, massa_a):
        m = assemble(massa_a).internal_manifest
        assert m.job_id and m.engine_version and m.dataset_fingerprint

    def test_nao_carrega_conteudo_analitico(self):
        bruto = massa_f()
        m = assemble(parse_facts(bruto)).internal_manifest
        texto = json.dumps(m.model_dump(mode="json"), ensure_ascii=False)
        for proibido in ("Cobrir intencoes sem amostra", "checkout", "0.8"):
            assert proibido not in texto

    def test_docstring_declara_que_nao_e_publicavel(self):
        from result_assembler.contracts import manifest

        doc = manifest.__doc__ or ""
        assert "NÃO é publicável" in doc

    def test_resultado_publico_continua_sem_os_identificadores(self, massa_a):
        publicado = serialize_canonical(assemble(massa_a).public_result).decode("utf-8")
        assert "job-massa-a" not in publicado
        assert "sentinela-engine-e7d0703" not in publicado
