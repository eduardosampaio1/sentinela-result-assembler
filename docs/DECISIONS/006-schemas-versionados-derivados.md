# ADR-006 — Schemas versionados e derivados da fonte tipada

**Decisão.** `schemas/*.schema.json` são **gerados** dos modelos pydantic por `scripts/generate_schemas.py`. Um teste regenera e compara com o arquivo em disco.

**Por quê.** Manter modelo, schema e documentação sincronizados à mão para de acontecer na terceira mudança — e aí o schema vira ficção que produtores externos usam para validar.

**Refinamento (Codex R2).** Restrições ficam no `Field`, não em validador customizado, sempre que o JSON Schema conseguir expressá-las. Validador customizado **não atravessa** para o schema, e o resultado é um contrato publicado **mais permissivo que o modelo**: o produtor valida contra ele, passa, e só descobre dentro da biblioteca. Em validador sobra apenas o que JSON não expressa (finitude).
