"""Falha se `schemas/*.schema.json` divergir do que os modelos geram.

Separado de `generate_schemas.py` de propósito: o gerador **escreve** e o verificador
**recusa**. Um script que faz as duas coisas acabaria "corrigindo" a divergência em vez de
denunciá-la — e aí o gate passaria sempre.
"""

from __future__ import annotations

import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "scripts"))

from generate_schemas import ALVOS, DESTINO, gerar, serializar  # noqa: E402


def main() -> int:
    defasados: list[str] = []
    for modelo, nome, schema_id in ALVOS:
        caminho = DESTINO / nome
        if not caminho.exists():
            defasados.append(f"{nome} (ausente)")
            continue
        if caminho.read_text(encoding="utf-8") != serializar(gerar(modelo, schema_id)):
            defasados.append(nome)

    if defasados:
        print("schemas defasados:", ", ".join(defasados))
        print("rode: python scripts/generate_schemas.py")
        return 1
    print(f"schemas sincronizados ({len(ALVOS)} arquivos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
