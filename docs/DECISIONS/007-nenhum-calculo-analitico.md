# ADR-007 — Nenhum cálculo analítico

**Decisão.** O assembler não calcula métrica alguma. A única operação que faz sobre um valor medido é **comparar** com a faixa contratada.

**Por quê.** Se ele calculasse qualquer coisa, existiriam duas fontes de verdade para aquele número — a do domínio e a dele — e a divergência apareceria como bug de dashboard meses depois, sem ninguém saber qual das duas está certa.

**Fronteira sutil.** Ele calcula **um** valor: o checksum SHA-256 do documento montado. É sobre bytes, não sobre analítica.

**Também proibido, e também não é "cálculo" à primeira vista:** converter razão em percentual, arredondar valor, somar parciais, preencher ausência. `display_precision` viaja como **sugestão**; o valor sai como o domínio o produziu — foi assim que `0.0042` sobreviveu.
