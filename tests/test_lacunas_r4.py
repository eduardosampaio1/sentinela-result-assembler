"""Lacunas apontadas pela revisão de qualidade dos testes (Codex R4).

Cada teste aqui fecha uma mutação que o Codex mostrou que sobreviveria à suíte. O nome da
mutação está no docstring — se alguém remover a regra, é este teste que cai.
"""

from __future__ import annotations

from typing import Any

import pytest

from massas import carregar_json, com_indicador, indice_de
from result_assembler import (
    AssemblyInvariantViolation,
    InvalidUnit,
    InvalidValue,
    UnsafeEvidence,
    assemble,
    parse_facts,
    serialize_canonical,
)

_TENANT = "engine.business.unit_economics.compute_tenant_metrics"
_HEALTH = "core._engine_helpers.build_ai_health_measurement"


@pytest.fixture
def bruto() -> dict[str, Any]:
    return carregar_json("massa_a_principal.facts.json")


def montar(payload: dict[str, Any]) -> None:
    assemble(parse_facts(payload))


class TestMoedaIso:
    """R4 [1] — `"dolar"` violava DUAS regras (tamanho e caixa). Remover a checagem de
    caixa deixaria o teste passando por causa do tamanho."""

    def test_codigo_minusculo_com_tres_letras_recusa(self, bruto):
        """Mutação alvo: remover `not ind.currency.isupper()`."""
        idx = indice_de(bruto, "total_estimated_cost")
        bruto["indicators"][idx]["currency"] = "usd"
        with pytest.raises(InvalidUnit):
            montar(bruto)

    def test_codigo_com_digito_recusa(self, bruto):
        """Mutação alvo: remover `not ind.currency.isalpha()`."""
        idx = indice_de(bruto, "total_estimated_cost")
        bruto["indicators"][idx]["currency"] = "US1"
        with pytest.raises(InvalidUnit):
            montar(bruto)

    def test_codigo_de_quatro_letras_recusa(self, bruto):
        idx = indice_de(bruto, "total_estimated_cost")
        bruto["indicators"][idx]["currency"] = "USDX"
        with pytest.raises(InvalidUnit):
            montar(bruto)


class TestMoedaSemValorMedido:
    """R4 [3] — o ramo `elif ind.currency` não tinha teste negativo. Declarar moeda em
    algo não medido sugere um valor que não veio."""

    def test_moeda_declarada_sem_valor_recusa(self, bruto):
        """Mutação alvo: remover o ramo `elif ind.currency`."""
        idx = indice_de(bruto, "cost_per_useful_outcome")
        bruto["indicators"][idx].update(
            {
                "availability": "unavailable",
                "reason": "no_input_data",
                "value": None,
                "denominator": None,
                "currency": "USD",
            }
        )
        with pytest.raises(InvalidUnit):
            montar(bruto)

    def test_sem_valor_e_sem_moeda_monta(self, bruto):
        idx = indice_de(bruto, "cost_per_useful_outcome")
        bruto["indicators"][idx].update(
            {
                "availability": "unavailable",
                "reason": "no_input_data",
                "value": None,
                "denominator": None,
                "currency": None,
            }
        )
        montar(bruto)


class TestCoberturaForaDoParcial:
    """R4 [4] — "available com cobertura declarada exige 1.0" não tinha teste. Sem ele, a
    montagem esconderia `coverage` e o defeito ficaria invisível."""

    def test_indicador_available_com_cobertura_parcial_recusa(self, bruto):
        """Mutação alvo: remover o bloco `elif availability is AVAILABLE and ...`."""
        with pytest.raises(AssemblyInvariantViolation):
            montar(com_indicador(bruto, data_coverage=0.5))

    def test_indicador_available_com_cobertura_1_monta(self, bruto):
        montar(com_indicador(bruto, data_coverage=1.0))

    def test_dimensao_available_com_cobertura_parcial_recusa(self, bruto):
        """Mutação alvo: remover o bloco equivalente em `_validar_dimensoes`."""
        payload = {
            **bruto,
            "dimensions": [
                {
                    "id": "economic",
                    "availability": "available",
                    "reason": "ok",
                    "value": 0.72,
                    "data_coverage": 0.5,
                    "calculation_version": "1.0",
                    "source": _HEALTH,
                }
            ],
        }
        with pytest.raises(AssemblyInvariantViolation):
            montar(payload)


class TestFaixaDeMoedaEEscalar:
    """R4 [5] — faixa negativa era testada só para razão e contagem. Custo e variância
    negativos passariam se a faixa do registro sumisse."""

    def test_moeda_negativa_recusa(self, bruto):
        """Mutação alvo: `valid_range=None` em `_moeda`."""
        idx = indice_de(bruto, "total_estimated_cost")
        bruto["indicators"][idx]["value"] = -1.0
        with pytest.raises(InvalidValue):
            montar(bruto)

    def test_escalar_negativo_recusa(self, bruto):
        """Mutação alvo: `valid_range=None` no `avg_variance_per_intent`.

        Variância negativa é matematicamente impossível — se aparecer, o produtor está
        errado, e publicar seria propagar o erro.
        """
        with pytest.raises(InvalidValue):
            montar(
                com_indicador(
                    bruto,
                    id="avg_variance_per_intent",
                    kind="scalar",
                    unit=None,
                    value=-0.5,
                    denominator=None,
                    source=_TENANT,
                )
            )

    def test_todo_indicador_do_registro_declara_faixa(self):
        """Prova estrutural, independente de massa: nenhum indicador pode ficar sem faixa
        contratada — é ela que impede valor impossível de virar resultado público."""
        from result_assembler import INDICATOR_REGISTRY

        sem_faixa = [i for i, d in INDICATOR_REGISTRY.items() if d.valid_range is None]
        assert sem_faixa == [], f"indicador sem faixa contratada: {sem_faixa}"


class TestVarreduraDosOutrosCamposPublicos:
    """R4 [6] — a parametrização só mexia em `evidence[0].label`. `kind` e `category`
    também são publicados."""

    SEGREDO = "Bearer sk-live-SEGREDO"

    def test_kind_de_evidencia_e_varrido(self):
        """Mutação alvo: remover `_varrer(ev.kind, ...)`."""
        f = carregar_json("massa_f_recomendacoes_evidencias.facts.json")
        f["evidence"][0]["kind"] = self.SEGREDO
        with pytest.raises(UnsafeEvidence):
            montar(f)

    def test_category_de_recomendacao_e_varrida(self):
        """Mutação alvo: remover `_varrer(rec.category, ...)`."""
        f = carregar_json("massa_f_recomendacoes_evidencias.facts.json")
        f["recommendations"][0]["category"] = "/var/lib/sentinela/jobs/an-1/dataset.jsonl"
        with pytest.raises(UnsafeEvidence):
            montar(f)


class TestDeterminismoNaoEConstante:
    """R4 [7] — os testes de determinismo comparavam duas saídas entre si; passariam com
    uma serialização que devolvesse bytes constantes."""

    def test_massas_diferentes_produzem_bytes_diferentes(self):
        """Contra-prova: se `serialize_canonical` fosse constante, isto cai."""
        nomes = [
            "massa_a_principal.facts.json",
            "massa_b_zero_e_nao_medido.facts.json",
            "massa_c_subcentavo.facts.json",
            "massa_d_parcial.facts.json",
            "massa_f_recomendacoes_evidencias.facts.json",
        ]
        bytes_por_massa = [
            serialize_canonical(assemble(parse_facts(carregar_json(n))).public_result)
            for n in nomes
        ]
        assert len(set(bytes_por_massa)) == len(nomes)

    def test_um_unico_campo_diferente_muda_os_bytes(self, bruto):
        """Granularidade: não basta massas diferentes darem bytes diferentes — mudar UM
        valor precisa mudar a saída."""
        base = serialize_canonical(assemble(parse_facts(bruto)).public_result)
        mexido = serialize_canonical(
            assemble(parse_facts(com_indicador(bruto, value=0.81))).public_result
        )
        assert base != mexido

    def test_serializacao_contem_o_conteudo_medido(self, bruto):
        """Prova positiva de conteúdo: os bytes carregam os valores, não um placeholder."""
        texto = serialize_canonical(assemble(parse_facts(bruto)).public_result).decode()
        assert '"useful_outcome_rate"' in texto
        assert "0.8" in texto
        assert "an-massa-a" in texto
