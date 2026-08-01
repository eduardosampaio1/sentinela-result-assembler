"""Determinismo — mesma entrada, mesmos bytes, mesmo checksum.

Não basta "os campos batem": o Result Store precisa poder comparar bytes. Cada teste aqui
ataca uma fonte diferente de variação que já quebrou serialização canônica em algum lugar.
"""

from __future__ import annotations

import copy
import json

import pytest

from massas import carregar_json
from result_assembler import (
    AnalysisFacts,
    assemble,
    checksum,
    serialize_canonical,
    to_canonical_dict,
)

TODAS = [
    "massa_a_principal.facts.json",
    "massa_b_zero_e_nao_medido.facts.json",
    "massa_c_subcentavo.facts.json",
    "massa_d_parcial.facts.json",
    "massa_f_recomendacoes_evidencias.facts.json",
]


@pytest.mark.determinism
@pytest.mark.parametrize("nome", TODAS)
def test_duas_montagens_produzem_bytes_identicos(nome):
    bruto = carregar_json(nome)
    a = assemble(AnalysisFacts.model_validate(bruto))
    b = assemble(AnalysisFacts.model_validate(copy.deepcopy(bruto)))
    assert serialize_canonical(a.public_result) == serialize_canonical(b.public_result)
    assert a.internal_manifest.result_checksum == b.internal_manifest.result_checksum


@pytest.mark.determinism
@pytest.mark.parametrize("nome", TODAS)
def test_ordem_das_chaves_do_payload_nao_muda_o_resultado(nome):
    """O produtor pode montar o dict em qualquer ordem. Se a ordem vazasse para os bytes,
    o checksum viraria função de quem montou o JSON, não do que foi medido."""
    bruto = carregar_json(nome)
    invertido = json.loads(json.dumps(bruto))
    invertido["indicators"] = list(reversed(invertido["indicators"]))
    invertido["recommendations"] = list(reversed(invertido.get("recommendations", [])))
    invertido["evidence"] = list(reversed(invertido.get("evidence", [])))
    invertido["dimensions"] = list(reversed(invertido.get("dimensions", [])))

    original = assemble(AnalysisFacts.model_validate(bruto))
    embaralhado = assemble(AnalysisFacts.model_validate(invertido))
    assert serialize_canonical(original.public_result) == serialize_canonical(
        embaralhado.public_result
    )


@pytest.mark.determinism
def test_checksum_muda_quando_o_conteudo_muda(massa_a):
    """Contra-prova: se o checksum fosse constante, o teste acima passaria por engano."""
    base = assemble(massa_a)
    bruto = carregar_json("massa_a_principal.facts.json")
    bruto["window"]["record_count"] = 101
    alterado = assemble(AnalysisFacts.model_validate(bruto))
    assert alterado.internal_manifest.result_checksum != base.internal_manifest.result_checksum


@pytest.mark.determinism
def test_checksum_do_manifesto_confere_com_os_bytes_publicados(massa_a):
    o = assemble(massa_a)
    assert o.internal_manifest.result_checksum == checksum(
        serialize_canonical(o.public_result)
    )
    assert o.internal_manifest.checksum_algorithm == "sha256"


@pytest.mark.determinism
def test_serializacao_e_utf8_sem_escape(massa_f):
    """Acento precisa sair como acento. `ensure_ascii=True` mudaria os bytes sem mudar o
    significado — e só em quem tem rótulo acentuado."""
    bruto = carregar_json("massa_f_recomendacoes_evidencias.facts.json")
    bruto["evidence"][0]["label"] = "segunda via de boleto"
    bruto["recommendations"][0]["title"] = "Revisão de limiar com acentuação"
    o = assemble(AnalysisFacts.model_validate(bruto))
    bytes_ = serialize_canonical(o.public_result)
    assert "acentuação".encode() in bytes_
    assert b"\\u00e7" not in bytes_


@pytest.mark.determinism
def test_json_gerado_e_parseavel_e_sem_nan(massa_d):
    o = assemble(massa_d)
    recarregado = json.loads(serialize_canonical(o.public_result).decode("utf-8"))
    assert recarregado == to_canonical_dict(o.public_result)
    texto = serialize_canonical(o.public_result).decode("utf-8")
    assert "NaN" not in texto and "Infinity" not in texto


@pytest.mark.determinism
def test_chaves_saem_ordenadas(massa_a):
    texto = serialize_canonical(assemble(massa_a).public_result).decode("utf-8")
    topo = json.loads(texto)
    assert list(topo.keys()) == sorted(topo.keys())
