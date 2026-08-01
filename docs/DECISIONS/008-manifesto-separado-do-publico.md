# ADR-008 — Manifesto interno separado do resultado público

**Decisão.** `assemble()` devolve dois objetos: `public_result` e `internal_manifest`.

**Por quê.** Proveniência técnica (job_id, engine_version, fingerprint, campos retidos, avisos) é necessária para operar e **não pode** ir ao consumidor. Um campo `_meta` dentro do próprio resultado seria esquecido e publicado.

**Regra do manifesto.** Ele registra **decisões**, não **conteúdo**: quais indicadores foram aceitos e quais campos ficaram retidos — nunca os valores medidos, os textos das recomendações ou as evidências. Assim pode ir para log e telemetria sem virar o vazamento que o resultado público evitou. Há teste que varre o manifesto atrás de valor medido.
