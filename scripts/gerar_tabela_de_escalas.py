"""Gera a tabela de escalas da `ANALYSIS-RESULT-V3-SPEC.md` a partir do CÓDIGO.

## Por que este script existe

A spec declarava `behavior_score` e `consistency_score` como `ratio_unit`. O produtor real mede
os dois em **0..100**, e publicar `54.46` sob `ratio_unit` faria o invariante de faixa do
`PublicMeasurement` **levantar** — a montagem recusaria.

A divergência entrou na D4 e **ninguém viu**, porque a tabela era prosa escrita à mão e nenhum
gate a comparava com o registro. Duas fontes de verdade para o mesmo fato, e a que ninguém
executa é a que passa a mentir.

## A direção da autoridade

O **código é canônico**: `_ESCALA_POR_SAIDA` (a faixa), `INDICATOR_REGISTRY` (a faixa dos
indicadores) e `argos_catalog` (identidade e nota). A spec passa a ser **derivada**, como os
tipos TypeScript já são derivados do schema.

Assim a spec não pode envelhecer em silêncio: ou ela é regenerada, ou o gate reprova.

## Uso

    python scripts/gerar_tabela_de_escalas.py            grava
    python scripts/gerar_tabela_de_escalas.py --check    só verifica (é o gate)
"""

from __future__ import annotations

import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from result_assembler.assembler.assemble_v3 import _ESCALA_POR_SAIDA  # noqa: E402
from result_assembler.registry.argos_catalog import POR_ID, Familia  # noqa: E402

SPEC = RAIZ / "docs" / "ANALYSIS-RESULT-V3-SPEC.md"

#: Delimitadores da região gerada. Fora deles, a spec continua sendo prosa humana — só a
#: TABELA é derivada, porque só ela duplica um fato que o código já declara.
INICIO = "<!-- GERADO: tabela de escalas — não editar à mão -->"
FIM = "<!-- FIM DO GERADO -->"


def linhas_da_familia(familia: str) -> list[str]:
    saidas = sorted(
        (o for o in POR_ID.values() if o.familia == familia and not o.bloqueio),
        key=lambda o: o.numero,
    )
    fora: list[str] = []
    for o in saidas:
        escala = _ESCALA_POR_SAIDA.get(o.public_id)
        # Saída sem escala declarada não é omitida: aparece como lacuna EXPLÍCITA, porque
        # sumir da tabela faria a spec descrever um catálogo menor do que o real.
        texto = f"`{escala.kind.value}`" if escala else "**sem escala declarada**"
        nota = (o.nota or "").replace("|", "\\|")
        fora.append(f"| `{o.public_id}` | {texto} | {nota} |")
    return fora


def tabela() -> str:
    partes = [
        INICIO,
        "",
        "> Derivada de `_ESCALA_POR_SAIDA` e do catálogo ARGOS por",
        "> `scripts/gerar_tabela_de_escalas.py`. O **código é canônico**: a escala é decisão do",
        "> PRODUTOR, e uma tabela escrita à mão já divergiu dele uma vez sem ninguém ver.",
        "",
        f"### `scores[]` — {len([o for o in POR_ID.values() if o.familia == Familia.SCORES])} entradas",
        "",
        "| public_id | escala | nota |",
        "|---|---|---|",
    ]
    partes += linhas_da_familia(Familia.SCORES)
    partes += ["", "### `risks[]`", "", "| public_id | escala | nota |", "|---|---|---|"]
    partes += linhas_da_familia(Familia.RISKS)
    partes += ["", "### `projections[]`", "", "| public_id | escala | nota |", "|---|---|---|"]
    partes += linhas_da_familia(Familia.PROJECTIONS)
    partes += ["", "### `intents[]`", "", "| public_id | escala | nota |", "|---|---|---|"]
    partes += linhas_da_familia(Familia.INTENTS)
    partes += ["", FIM]
    return "\n".join(partes)


def aplicar(texto: str, bloco: str) -> str:
    if INICIO in texto and FIM in texto:
        i = texto.index(INICIO)
        j = texto.index(FIM) + len(FIM)
        return texto[:i] + bloco + texto[j:]
    raise SystemExit(
        f"marcadores nao encontrados em {SPEC.name}: insira {INICIO!r} e {FIM!r} "
        "em volta da tabela de escalas"
    )


def main() -> int:
    checar = "--check" in sys.argv
    atual = SPEC.read_text(encoding="utf-8")
    novo = aplicar(atual, tabela())
    if checar:
        if atual != novo:
            print(
                "tabela de escalas DESATUALIZADA em relacao ao registro.\n"
                "Rode: python scripts/gerar_tabela_de_escalas.py",
                file=sys.stderr,
            )
            return 1
        print("tabela de escalas em dia")
        return 0
    SPEC.write_text(novo, encoding="utf-8")
    print(f"gravado: {SPEC.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
