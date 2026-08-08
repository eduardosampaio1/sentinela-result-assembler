"""Serialização canônica e checksum.

Determinismo aqui não é detalhe de implementação — é o que permite ao Result Store dizer
"este resultado é o mesmo de antes" sem comparar semanticamente, e ao operador provar que
uma remontagem não mudou nada.

Escolhas, e o que cada uma evita:

- `sort_keys=True` — a ordem de inserção de dict do Python é estável, mas depende da
  ordem em que o produtor montou. Ordenar tira essa dependência.
- `ensure_ascii=False` + UTF-8 explícito — sem isto, um rótulo acentuado sairia como
  `\\u00e1` em um ambiente e como `á` em outro, mudando os bytes sem mudar o significado.
- `separators` sem espaço — remove a variação de formatação entre versões do runtime.
- `allow_nan=False` — `NaN`/`Infinity` não são JSON válido; deixá-los passar produziria um
  documento que alguns parsers aceitam e outros rejeitam. Aqui é erro, não surpresa.
- floats saem pelo `repr` do Python, que é o shortest round-trip desde a 3.1: `0.0042`
  serializa como `0.0042`, não como `0.0042000000000000002`.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from result_assembler.contracts.result import PublicResult
from result_assembler.contracts.result_v2 import PublicResultV2

#: Nome do algoritmo publicado no manifesto, para o verificador não adivinhar.
CHECKSUM_ALGORITHM = "sha256"


def to_canonical_dict(result: PublicResult | PublicResultV2) -> dict[str, Any]:
    """`PublicResult` → dict JSON-compatível, sem objetos do pydantic nem enums."""
    # `mode="json"` converte enums em seus valores e tuplas em listas — o que sai já é
    # exatamente o que o JSON vai conter.
    return result.model_dump(mode="json")


def serialize_canonical(result: PublicResult | PublicResultV2) -> bytes:
    """Serializa o resultado público em bytes canônicos e estáveis."""
    return json.dumps(
        to_canonical_dict(result),
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def checksum(payload: bytes) -> str:
    """SHA-256 hexadecimal dos bytes canônicos."""
    return hashlib.sha256(payload).hexdigest()
