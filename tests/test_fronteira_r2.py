"""Achados da revisão de arquitetura (Codex R2) que viraram comportamento contratado."""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest

from massas import carregar_json, com_indicador
from result_assembler import (
    AnalysisFacts,
    AssemblyError,
    InvalidValue,
    SchemaMismatch,
    assemble,
    parse_facts,
    serialize_canonical,
)

RAIZ = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture
def bruto() -> dict[str, Any]:
    return carregar_json("massa_a_principal.facts.json")


class TestPortaPublicaDeEntrada:
    """Codex R2 [5] — `model_validate` levanta `pydantic.ValidationError`, que não é
    `AssemblyError`. Um consumidor que capturasse só as categorias da biblioteca perderia
    campo extra, `NaN`, bool e string numérica."""

    @pytest.mark.parametrize(
        "campos",
        [
            {"campo_que_o_dominio_inventou": 1},
            {"value": float("nan")},
            {"value": True},
            {"value": "0"},
            {"kind": "kind_inexistente"},
        ],
    )
    def test_todo_erro_de_forma_vira_assembly_error(self, bruto, campos):
        with pytest.raises(AssemblyError) as exc:
            parse_facts(com_indicador(bruto, **campos))
        assert isinstance(exc.value, SchemaMismatch)

    def test_mensagem_localiza_sem_ecoar_o_payload(self, bruto):
        segredo = "VALOR-QUE-NAO-PODE-APARECER"
        with pytest.raises(SchemaMismatch) as exc:
            parse_facts(com_indicador(bruto, value=segredo))
        assert segredo not in str(exc.value)
        assert "indicators" in str(exc.value)

    def test_payload_valido_atravessa(self, bruto):
        facts = parse_facts(bruto)
        assert isinstance(facts, AnalysisFacts)
        assemble(facts)

    def test_payload_que_nem_e_objeto_recusa(self):
        with pytest.raises(SchemaMismatch):
            parse_facts("isto nao e um envelope")


class TestSchemaNaoEMaisPermissivoQueOModelo:
    """Codex R2 [2] e [3] — um schema mais permissivo que o modelo é pior que schema
    nenhum: o produtor valida contra ele, passa, e só descobre na biblioteca."""

    @staticmethod
    def _facts_schema() -> dict[str, Any]:
        return json.loads(
            (RAIZ / "schemas" / "analysis-facts-v1.schema.json").read_text(encoding="utf-8")
        )

    def test_denominador_positivo_esta_no_schema(self):
        d = self._facts_schema()["$defs"]["Denominator"]["properties"]["value"]
        assert d.get("exclusiveMinimum") == 0

    def test_faixa_da_cobertura_esta_no_schema(self):
        cov = self._facts_schema()["$defs"]["FactIndicator"]["properties"]["data_coverage"]
        numerico = [x for x in cov["anyOf"] if x.get("type") == "number"]
        assert numerico and numerico[0]["minimum"] == 0.0 and numerico[0]["maximum"] == 1.0

    def test_faixa_da_dimensao_esta_no_schema(self):
        val = self._facts_schema()["$defs"]["FactDimension"]["properties"]["value"]
        numerico = [x for x in val["anyOf"] if x.get("type") == "number"]
        assert numerico and numerico[0]["minimum"] == 0.0 and numerico[0]["maximum"] == 1.0

    def test_contadores_estao_no_schema(self):
        props = self._facts_schema()["$defs"]["FactIndicator"]["properties"]
        obs = [x for x in props["observed_units"]["anyOf"] if x.get("type") == "integer"]
        esp = [x for x in props["expected_units"]["anyOf"] if x.get("type") == "integer"]
        assert obs and obs[0]["minimum"] == 0
        assert esp and esp[0]["exclusiveMinimum"] == 0

    def test_o_que_o_schema_aceita_o_modelo_tambem_aceita(self, bruto):
        """A propriedade que importa: nenhum payload válido pelo schema pode ser recusado
        pelo modelo por uma restrição que o schema não expressa."""
        import jsonschema

        schema = self._facts_schema()
        payload = com_indicador(bruto, denominator={"kind": "analyzed_conversations", "value": 1})
        jsonschema.validate(instance=payload, schema=schema)
        parse_facts(payload)  # não pode levantar


class TestOrdemDeEvidenceRefs:
    """Codex R2 [4] — `evidence_refs` é um CONJUNTO de referências, não uma sequência com
    significado. Sem ordenar, duas entradas equivalentes gerariam checksums diferentes."""

    def _com_refs(self, refs: list[str]) -> dict[str, Any]:
        base = carregar_json("massa_f_recomendacoes_evidencias.facts.json")
        for rec in base["recommendations"]:
            if rec["id"] == "rec-a":
                rec["evidence_refs"] = refs
        return base

    def test_ordem_das_refs_nao_muda_os_bytes(self):
        a = assemble(parse_facts(self._com_refs(["ev-1", "ev-2"])))
        b = assemble(parse_facts(self._com_refs(["ev-2", "ev-1"])))
        assert serialize_canonical(a.public_result) == serialize_canonical(b.public_result)
        assert a.internal_manifest.result_checksum == b.internal_manifest.result_checksum

    def test_refs_saem_ordenadas(self):
        r = assemble(parse_facts(self._com_refs(["ev-2", "ev-1"]))).public_result
        rec = next(x for x in r.recommendations if x.id == "rec-a")
        assert rec.evidence_refs == ("ev-1", "ev-2")


class TestOrigemDaDimensao:
    """Codex R2 [1] — indicadores exigiam origem registrada; dimensões não exigiam."""

    def test_origem_nao_aceita_recusa(self, bruto):
        payload = {
            **bruto,
            "dimensions": [
                {
                    "id": "economic",
                    "availability": "available",
                    "reason": "ok",
                    "value": 0.72,
                    "data_coverage": None,
                    "calculation_version": "1.0",
                    "source": "algum.modulo.improvisado",
                }
            ],
        }
        with pytest.raises(InvalidValue):
            assemble(parse_facts(payload))
