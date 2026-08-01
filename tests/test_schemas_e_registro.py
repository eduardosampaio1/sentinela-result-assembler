"""Sincronização dos schemas e coerência do registro.

Documentação, modelo e schema divergirem em silêncio é o modo de falha clássico de
contrato versionado. Aqui divergir quebra o gate.
"""

from __future__ import annotations

import json
import pathlib
import sys

import jsonschema
import pytest

from massas import carregar_json
from result_assembler import (
    CANONICAL_ORDER,
    INDICATOR_REGISTRY,
    SUPPORTED_DIMENSION_IDS,
    AnalysisFacts,
    assemble,
    to_canonical_dict,
)
from result_assembler.contracts.facts import Availability, IndicatorKind
from result_assembler.errors import ERROR_CATEGORIES

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

from generate_schemas import ALVOS, gerar, serializar  # noqa: E402

MASSAS = [p.name for p in sorted((RAIZ / "fixtures").glob("*.facts.json"))]


class TestSincronizacaoDeSchemas:
    @pytest.mark.parametrize("modelo,nome,schema_id", ALVOS)
    def test_arquivo_em_disco_bate_com_o_modelo(self, modelo, nome, schema_id):
        """Se alguém mudar o modelo e esquecer `python scripts/generate_schemas.py`,
        é AQUI que descobre — não em produção."""
        em_disco = (RAIZ / "schemas" / nome).read_text(encoding="utf-8")
        assert em_disco == serializar(gerar(modelo, schema_id)), (
            f"schemas/{nome} está defasado — rode `python scripts/generate_schemas.py`"
        )

    @pytest.mark.parametrize("nome", MASSAS)
    def test_toda_massa_valida_contra_o_schema_de_entrada(self, nome):
        schema = json.loads(
            (RAIZ / "schemas" / "analysis-facts-v1.schema.json").read_text(encoding="utf-8")
        )
        jsonschema.validate(instance=carregar_json(nome), schema=schema)

    @pytest.mark.parametrize(
        "nome",
        [m for m in MASSAS if "versao_incompativel" not in m],
    )
    def test_todo_resultado_montado_valida_contra_o_schema_de_saida(self, nome):
        schema = json.loads(
            (RAIZ / "schemas" / "analysis-result-v1.schema.json").read_text(encoding="utf-8")
        )
        montado = assemble(AnalysisFacts.model_validate(carregar_json(nome)))
        saida = to_canonical_dict(montado.public_result)
        jsonschema.validate(instance=saida, schema=schema)

    def test_schema_de_saida_proibe_campo_extra(self):
        """`additionalProperties: false` é o que impede um campo interno de aparecer no
        público sem alguém decidir."""
        schema = json.loads(
            (RAIZ / "schemas" / "analysis-result-v1.schema.json").read_text(encoding="utf-8")
        )
        assert schema.get("additionalProperties") is False
        for nome, definicao in schema.get("$defs", {}).items():
            if definicao.get("type") == "object":
                assert definicao.get("additionalProperties") is False, (
                    f"$defs.{nome} aceitaria campo não contratado"
                )


class TestRegistro:
    def test_ordem_canonica_cobre_exatamente_o_registro(self):
        """Um indicador registrado fora da ordem canônica nunca seria publicado — e o
        registro estaria mentindo sobre o que suporta."""
        assert set(CANONICAL_ORDER) == set(INDICATOR_REGISTRY)
        assert len(CANONICAL_ORDER) == len(set(CANONICAL_ORDER))

    def test_ids_publicos_sao_unicos(self):
        publicos = [d.public_id for d in INDICATOR_REGISTRY.values()]
        assert len(publicos) == len(set(publicos))

    def test_razoes_declaram_faixa_zero_um_e_denominador(self):
        for interno, d in INDICATOR_REGISTRY.items():
            if d.kind is IndicatorKind.RATIO:
                assert d.valid_range == (0.0, 1.0), f"{interno}: razão sem faixa 0..1"
                assert d.denominator_kind, f"{interno}: razão sem denominador contratado"

    def test_contagens_nao_admitem_negativo_nem_percentual(self):
        for interno, d in INDICATOR_REGISTRY.items():
            if d.kind is IndicatorKind.COUNT:
                assert d.valid_range is not None and d.valid_range[0] == 0.0
                assert d.unit != "ratio", f"{interno}: contagem com unidade de razão"
                assert d.display_precision == 0

    def test_todo_indicador_declara_origem_e_versao(self):
        for interno, d in INDICATOR_REGISTRY.items():
            assert d.accepted_sources, f"{interno}: sem origem analítica aceita"
            assert d.accepted_calculation_versions, f"{interno}: sem versão de cálculo"
            assert d.description.strip(), f"{interno}: sem descrição"

    def test_todo_indicador_aceita_os_cinco_estados(self):
        """Nenhum indicador pode ser obrigado a ter valor: qualquer um pode não ter sido
        medido nesta análise."""
        for interno, d in INDICATOR_REGISTRY.items():
            assert set(d.allowed_availability) == set(Availability), interno

    def test_metricas_de_semantica_duvidosa_ficam_fora(self):
        """Cadeado do discovery: `handoff_rate` é `1 - useful_rate` no produtor (deu 0.2
        com ZERO handoffs) e `token_waste_estimate` é anotado `# proxy` no engine.
        Nenhum dos dois pode virar indicador público sem revisão semântica."""
        fora = {
            "handoff_rate",
            "token_waste_estimate",
            "token_waste_per_session",
            "estimated_wasted_tokens_total",
        }
        assert fora & set(INDICATOR_REGISTRY) == set(), (
            "métrica de semântica não resolvida entrou no registro"
        )

    def test_dimensoes_suportadas_sao_as_quatro_do_composto(self):
        assert frozenset(
            {"semantic", "behavioral", "structural", "economic"}
        ) == SUPPORTED_DIMENSION_IDS


class TestErros:
    def test_categorias_sao_unicas_e_estaveis(self):
        assert len(ERROR_CATEGORIES) == len(set(ERROR_CATEGORIES))
        assert "unknown_indicator" in ERROR_CATEGORIES
        assert "unsafe_evidence" in ERROR_CATEGORIES

    def test_toda_categoria_tem_classe_exportada(self):
        import result_assembler as ra
        from result_assembler.errors import AssemblyError

        classes = {
            getattr(ra, n).category
            for n in ra.__all__
            if isinstance(getattr(ra, n), type) and issubclass(getattr(ra, n), AssemblyError)
        }
        assert set(ERROR_CATEGORIES) <= classes
