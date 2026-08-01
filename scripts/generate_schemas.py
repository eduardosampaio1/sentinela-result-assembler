"""Gera `schemas/*.schema.json` a partir dos modelos tipados.

Fonte única: os modelos pydantic. O JSON Schema é **derivado**, nunca escrito à mão —
manter modelo, schema e documentação sincronizados manualmente é o tipo de trabalho que
para de acontecer na terceira mudança, e aí o schema vira ficção.

`tests/test_schema_sync.py` roda esta mesma função e falha se o arquivo em disco divergir,
então esquecer de regenerar quebra o gate em vez de passar batido.

Uso::

    python scripts/generate_schemas.py
"""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from result_assembler.contracts.facts import AnalysisFacts  # noqa: E402
from result_assembler.contracts.result import PublicResult  # noqa: E402
from result_assembler.version import (  # noqa: E402
    FACTS_SCHEMA_VERSION,
    RESULT_SCHEMA_VERSION,
)

DESTINO = RAIZ / "schemas"

#: (modelo, nome do arquivo, `$id`) — a lista é o contrato do que existe publicado.
ALVOS: tuple[tuple[type, str, str], ...] = (
    (AnalysisFacts, f"{FACTS_SCHEMA_VERSION}.schema.json", FACTS_SCHEMA_VERSION),
    (PublicResult, f"{RESULT_SCHEMA_VERSION}.schema.json", RESULT_SCHEMA_VERSION),
)


def gerar(modelo: type, schema_id: str) -> dict[str, Any]:
    """JSON Schema do modelo, com `$id` estável e chaves ordenadas."""
    schema: dict[str, Any] = modelo.model_json_schema(mode="serialization")  # type: ignore[attr-defined]
    schema["$id"] = schema_id
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return schema


def serializar(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    DESTINO.mkdir(exist_ok=True)
    for modelo, nome, schema_id in ALVOS:
        caminho = DESTINO / nome
        caminho.write_text(serializar(gerar(modelo, schema_id)), encoding="utf-8")
        print(f"gerado: schemas/{nome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
