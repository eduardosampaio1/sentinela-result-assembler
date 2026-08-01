# ADR-001 — Repositório independente

**Contexto.** O montador do resultado poderia viver dentro de `sentinela` (perto dos produtores) ou de `sentinela-orchestrator` (perto do Result Store).

**Decisão.** Repositório próprio: `sentinela-result-assembler`.

**Por quê.** Dentro do `sentinela`, nada impediria o assembler de chamar um produtor "só desta vez" — e a fronteira que ele existe para criar morreria no primeiro atalho. Dentro do orchestrator, ele herdaria banco e HTTP. Separado, a proibição de calcular não depende de disciplina: **o código analítico não está no caminho de import**.

**Custo aceito.** Uma dependência a mais para operar e um passo de versionamento na integração.
