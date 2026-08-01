# ADR-005 — O assembler não tem relógio

**Decisão.** `analyzed_at` é campo **obrigatório** dos fatos. Nenhum módulo do pacote importa `datetime`, `time` ou `uuid`.

**Por quê.** Uma data gerada na montagem seria a hora da MONTAGEM, não a da ANÁLISE. As duas coincidem no caminho feliz e divergem exatamente quando importa: remontagem, reprocessamento, migração. E quebraria o determinismo do ADR-004.

**Como é provado.** Cadeado AST sobre os imports do pacote + mutação `m3` (gerar a data localmente), que mata a suíte.
