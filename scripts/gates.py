"""Todos os quality gates, na ordem, com veredito por gate.

Roda igual na máquina de quem desenvolve e num CI — sem YAML de provedor nenhum, porque
"passa no CI" não pode ser a única forma de descobrir que algo quebrou.

Uso::

    python scripts/gates.py            # todos
    python scripts/gates.py --rapido   # pula build e auditoria de dependências
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable

GATES: list[tuple[str, list[str], bool]] = [
    ("lint", [PY, "-m", "ruff", "check", "src", "tests", "scripts"], False),
    ("format", [PY, "-m", "ruff", "format", "--check", "src", "tests", "scripts"], False),
    ("typecheck", [PY, "-m", "mypy"], False),
    ("schemas", [PY, "scripts/verify_schemas.py"], False),
    (
        "testes",
        [
            PY,
            "-m",
            "pytest",
            "tests/",
            "-q",
            "--cov=result_assembler",
            "--cov-report=term:skip-covered",
        ],
        False,
    ),
    ("build", [PY, "-m", "build", "--wheel", "--outdir", "dist"], True),
    (
        "dependencias",
        [PY, "-m", "pip_audit", "-r", "requirements.txt", "--progress-spinner", "off"],
        True,
    ),
]


def main() -> int:
    rapido = "--rapido" in sys.argv
    ambiente = {**os.environ, "PYTHONPATH": str(RAIZ / "src")}
    falhas: list[str] = []

    for nome, comando, lento in GATES:
        if rapido and lento:
            print(f"[{nome:14s}] PULADO (--rapido)")
            continue
        r = subprocess.run(comando, cwd=RAIZ, capture_output=True, text=True, env=ambiente)
        ok = r.returncode == 0
        print(f"[{nome:14s}] {'OK' if ok else 'FALHOU'}")
        if not ok:
            falhas.append(nome)
            print((r.stdout + r.stderr).strip()[-2000:])

    print("-" * 60)
    if falhas:
        print(f"GATES REPROVADOS: {', '.join(falhas)}")
        return 1
    print("TODOS OS GATES PASSARAM")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
