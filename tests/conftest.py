"""Fixtures das massas. Uma fonte só, para nenhum teste inventar a sua."""

from __future__ import annotations

import sys
from typing import Any

import pytest

# O pacote vive em `src/`; sem instalação editável, é isto que o torna importável.
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "src"))

from massas import carregar, carregar_json  # noqa: E402

from result_assembler import AnalysisFacts  # noqa: E402


@pytest.fixture
def massa_a() -> AnalysisFacts:
    """Principal: 100 registros, 80 úteis, custo 10.00 → CPUO 0.125. Tudo medido."""
    return carregar("massa_a_principal.facts.json")


@pytest.fixture
def massa_b() -> AnalysisFacts:
    """Zero REAL convivendo com NÃO MEDIDO no mesmo documento."""
    return carregar("massa_b_zero_e_nao_medido.facts.json")


@pytest.fixture
def massa_c() -> AnalysisFacts:
    """Sub-centavo: 0.0042 e 5e-06."""
    return carregar("massa_c_subcentavo.facts.json")


@pytest.fixture
def massa_d() -> AnalysisFacts:
    """Parcial: os cinco estados de disponibilidade num documento só."""
    return carregar("massa_d_parcial.facts.json")


@pytest.fixture
def massa_e_json() -> dict[str, Any]:
    """Versão de medição incompatível — o teste monta e espera a recusa."""
    return carregar_json("massa_e_versao_incompativel.facts.json")


@pytest.fixture
def massa_f() -> AnalysisFacts:
    """Recomendações (fora de ordem no payload) + evidências."""
    return carregar("massa_f_recomendacoes_evidencias.facts.json")
