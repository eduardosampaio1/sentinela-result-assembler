# ADR-009 — Nenhuma integração de rede nesta entrega

**Decisão.** Sem Result Store, Gateway, HTTP, fila, persistência ou deploy. Nenhum dos três repositórios existentes foi alterado.

**Por quê.** O Discovery mostrou que **nenhum produtor emite `analysis-facts-v1` hoje** (lacuna L1) e que três campos de que a integração vai precisar não existem ainda no domínio (L2 `calculation_version`, L3 `measurement_contract_version` preenchida, L4 código de moeda). Integrar agora significaria inventar esses campos do lado de cá — exatamente o que este pacote existe para impedir.

**O que fica pronto.** O contrato de entrada **é** a especificação do que pedir ao produtor. `docs/INTEGRATION.md` lista as lacunas em ordem de dependência.
