# ADR-004 — Saída determinística byte a byte

**Decisão.** Mesma entrada → mesmos bytes → mesmo checksum.

Quatro fontes de variação eliminadas:

| Fonte | Eliminação |
|---|---|
| ordem de chegada dos indicadores | publicação segue `CANONICAL_ORDER` do registro |
| ordem de chaves no JSON | `sort_keys=True` |
| encoding | `ensure_ascii=False` + UTF-8 explícito |
| relógio / aleatoriedade / estado global | não existem no pacote |

**Por quê.** Sem isto, o Result Store não consegue dizer "este resultado é o mesmo de antes" sem comparar semanticamente, e nenhum operador consegue provar que uma remontagem não mudou nada.

**Consequências.** Datas entram como fato. Ordem de recomendação entra como fato (`order`). `evidence_refs` sai **ordenado** — é conjunto de referências, não sequência com significado.
