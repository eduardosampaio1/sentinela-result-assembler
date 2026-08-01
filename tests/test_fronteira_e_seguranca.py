"""Fronteira pública e segurança — o que NÃO pode sair.

A prova forte é estrutural: os bytes publicados são varridos em busca de qualquer valor
interno que a massa carregava. Um teste que só conferisse "o campo X não está no modelo"
passaria mesmo se o valor vazasse dentro de outro campo.
"""

from __future__ import annotations

import pytest

from massas import carregar_json
from result_assembler import AnalysisFacts, UnsafeEvidence, assemble, serialize_canonical


@pytest.mark.security
def test_nenhum_valor_interno_aparece_nos_bytes_publicos(massa_a):
    """Varredura por VALOR, não por nome de campo: se `job-massa-a` aparecesse em qualquer
    lugar do documento — inclusive dentro de outro campo — isto pega.

    Só entram aqui valores DISTINTIVOS. `calculation_version="1.0"` ficou de fora de
    propósito: "1.0" aparece naturalmente como número no JSON, e uma varredura por
    substring não sabe distinguir vazamento de coincidência. Para esse campo a prova certa
    é a estrutural, no teste seguinte.
    """
    o = assemble(massa_a)
    publicado = serialize_canonical(o.public_result).decode("utf-8")

    internos = [
        massa_a.identity.job_id,
        massa_a.identity.analysis_run_id,
        massa_a.provenance.engine_version,
        massa_a.provenance.dataset_fingerprint,
        massa_a.indicators[0].source,
    ]
    vazados = [v for v in internos if v and v in publicado]
    assert vazados == [], f"valor interno vazou para o resultado público: {vazados}"


@pytest.mark.security
def test_nenhum_modelo_publico_declara_campo_interno():
    """Prova estrutural: os campos internos não existem no contrato público.

    Vale para os que a varredura por valor não alcança (`calculation_version`, `reason`,
    `observed_units`), e é a garantia que sobrevive a qualquer massa.
    """
    from result_assembler.contracts.result import (
        PublicDimension,
        PublicEvidenceSummary,
        PublicIndicator,
        PublicRecommendation,
        PublicResult,
        PublicSummary,
    )

    proibidos = {
        "calculation_version",
        "source",
        "reason",
        "observed_units",
        "expected_units",
        "job_id",
        "analysis_run_id",
        "engine_version",
        "analysis_version",
        "dataset_fingerprint",
    }
    modelos = (
        PublicResult,
        PublicIndicator,
        PublicDimension,
        PublicRecommendation,
        PublicEvidenceSummary,
        PublicSummary,
    )
    achados = [
        f"{m.__name__}.{campo}"
        for m in modelos
        for campo in m.model_fields
        if campo in proibidos
    ]
    assert achados == [], f"contrato público declara campo interno: {achados}"


@pytest.mark.security
def test_ids_internos_de_indicador_nao_viram_ids_publicos(massa_a):
    """O id interno (`useful_rate`) não é o id público (`useful_outcome_rate`). Publicar o
    interno acoplaria o consumidor ao nome que o produtor usa por dentro."""
    o = assemble(massa_a)
    publicos = {i.id for i in o.public_result.indicators}
    internos = {i.id for i in massa_a.indicators}
    assert "useful_outcome_rate" in publicos
    assert "useful_rate" not in publicos
    # A interseção é aceitável só onde o registro mapeia o nome para ele mesmo.
    assert internos - publicos, "nenhum id foi renomeado — o mapeamento não está agindo"


@pytest.mark.security
def test_manifesto_guarda_o_que_o_publico_nao_carrega(massa_a):
    m = assemble(massa_a).internal_manifest
    assert m.job_id == "job-massa-a"
    assert m.engine_version == "sentinela-engine-e7d0703"
    assert "identity.job_id" in m.withheld_internal_fields
    assert "provenance.engine_version" in m.withheld_internal_fields


@pytest.mark.security
def test_manifesto_nao_carrega_valores_medidos(massa_a):
    """O manifesto vai para log/telemetria. Se levasse valores, seria o vazamento que o
    resultado público evitou."""
    import json

    texto = json.dumps(assemble(massa_a).internal_manifest.model_dump(mode="json"))
    for proibido in ("0.125", "0.85", "10.0"):
        assert proibido not in texto, f"manifesto carregou valor medido: {proibido}"


@pytest.mark.security
@pytest.mark.parametrize(
    "conteudo",
    [
        "/var/lib/sentinela/jobs/an-1/dataset.jsonl",
        "C:\\Users\\op\\secret.txt",
        "https://minio.internal/bucket/key?X-Amz-Signature=abc",
        "Bearer eyJhbGciOiJIUzI1NiJ9",
        "Traceback (most recent call last)",
        "ValueError: intent not found",
        "select * from orchestrator_analysis_results",
        "worker_id=w-17",
        "s3 object_key=an-1/raw.jsonl",
        "-----BEGIN RSA PRIVATE KEY-----",
    ],
)
def test_evidencia_com_conteudo_proibido_recusa(conteudo):
    bruto = carregar_json("massa_f_recomendacoes_evidencias.facts.json")
    bruto["evidence"][0]["label"] = conteudo
    with pytest.raises(UnsafeEvidence):
        assemble(AnalysisFacts.model_validate(bruto))


@pytest.mark.security
def test_titulo_de_recomendacao_tambem_e_varrido():
    """O título é texto público exibido ao usuário — mesma régua da evidência."""
    bruto = carregar_json("massa_f_recomendacoes_evidencias.facts.json")
    bruto["recommendations"][0]["title"] = "Ver traceback em /opt/app/logs/erro.log"
    with pytest.raises(UnsafeEvidence):
        assemble(AnalysisFacts.model_validate(bruto))


@pytest.mark.security
def test_rotulo_longo_demais_recusa():
    bruto = carregar_json("massa_f_recomendacoes_evidencias.facts.json")
    bruto["evidence"][0]["label"] = "x" * 500
    with pytest.raises(UnsafeEvidence):
        assemble(AnalysisFacts.model_validate(bruto))


@pytest.mark.security
def test_mensagem_de_erro_nao_ecoa_o_conteudo_proibido():
    """Ecoar o trecho copiaria o segredo para o log — que é o que se quer evitar."""
    bruto = carregar_json("massa_f_recomendacoes_evidencias.facts.json")
    segredo = "Bearer eyJhbGciOiJIUzI1NiJ9-SEGREDO"
    bruto["evidence"][0]["label"] = segredo
    with pytest.raises(UnsafeEvidence) as exc:
        assemble(AnalysisFacts.model_validate(bruto))
    assert segredo not in str(exc.value)
    assert "evidence[0].label" in str(exc.value)


@pytest.mark.security
def test_erro_de_valor_nao_ecoa_o_valor_medido():
    from massas import com_indicador
    from result_assembler import InvalidValue

    bruto = carregar_json("massa_a_principal.facts.json")
    with pytest.raises(InvalidValue) as exc:
        assemble(AnalysisFacts.model_validate(com_indicador(bruto, value=1.4142135)))
    assert "1.4142135" not in str(exc.value)
    assert "indicators[0].value" in str(exc.value)
