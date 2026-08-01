"""Acesso às massas. Módulo simples (não pacote) para os testes importarem direto."""

from __future__ import annotations

import copy
import json
import pathlib
from typing import Any

from result_assembler import AnalysisFacts

FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "fixtures"


def carregar_json(nome: str) -> dict[str, Any]:
    """Payload cru — para os testes que precisam mutar UM campo antes de validar."""
    dados: dict[str, Any] = json.loads((FIXTURES / nome).read_text(encoding="utf-8"))
    return dados


def carregar(nome: str) -> AnalysisFacts:
    return AnalysisFacts.model_validate(carregar_json(nome))


def com_indicador(base: dict[str, Any], **campos: Any) -> dict[str, Any]:
    """Copia a massa e sobrescreve campos do PRIMEIRO indicador.

    Mudar um campo só é deliberado: se o teste montasse um payload próprio, ele passaria a
    provar aquele payload. Partindo de uma massa que comprovadamente monta, a única
    explicação para a recusa é a regra sob teste.
    """
    novo = copy.deepcopy(base)
    novo["indicators"][0].update(campos)
    return novo


def indice_de(base: dict[str, Any], indicator_id: str) -> int:
    """Posição de um indicador na massa, por id."""
    for i, item in enumerate(base["indicators"]):
        if item["id"] == indicator_id:
            return i
    raise AssertionError(f"indicador ausente na massa: {indicator_id}")
