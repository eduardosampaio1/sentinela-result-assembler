# ADR-002 — Núcleo como biblioteca pura

**Decisão.** Sem FastAPI, banco, Redis, fila, filesystem compartilhado ou variável de ambiente. Uma dependência de runtime: `pydantic`.

**Por quê.** Um serviço HTTP obrigaria a decidir agora autenticação, versionamento de rota, health check e deploy — decisões que pertencem a quem integrar e que ficariam congeladas antes da primeira necessidade real. Como biblioteca, o Orchestrator importa direto; se depois for preciso um serviço, ele embrulha isto sem reescrever nada.

**Consequência verificável.** `requirements.txt` tem uma linha. Um cadeado AST proíbe `os`, `datetime`, `random`, `time`, `uuid` e `secrets` dentro do pacote.
