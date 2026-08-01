# Migração — perfil provisório da E5 → `analysis-result-v1`

O frontend (`sentinela-front @ bd4d156`) tem um perfil provisório isolado em `src/features/canonical-analysis/result/`: `provisional-analysis-result-v1`. Ele foi construído sob decisão de produto explícita, com massa sintética, porque o contrato público não existia.

**Este documento não altera o frontend.** É o guia para uma etapa posterior.

## Por que a migração é barata

Só **três arquivos** do frontend conhecem o shape (`provisionalSchema.ts`, `validator.ts`, `adapter.ts`). A UI consome um view model. Trocar a fronteira **não exige reconstruir a interface**.

## Tabela de correspondência

### Envelope

| E5 provisório | `analysis-result-v1` | Situação |
|---|---|---|
| `schema` (dentro do blob) | `result_schema_version` (do envelope público) | **corrigido** — a E5 já migrou para o campo contratado como autoridade |
| — | `measurement_contract_version` | **novo** — o consumidor precisa dele para não comparar resultados de contratos diferentes |
| `summary.total_records` | `summary.record_count` | renomeado |
| `summary.useful_outcomes` | indicador `useful_outcome_count` | **movido** — é medição, com estado próprio; no envelope não podia expressar ausência |
| `summary.analyzed_at` | `summary.analyzed_at` | mantido |
| — | `partiality.complete` / `.reasons` | **novo** — a E5 inferia parcialidade contando indicadores sem descriptor |

### Indicador

| E5 provisório | `analysis-result-v1` | Situação |
|---|---|---|
| `id` | `id` (**público**) | renomeado por indicador — ver abaixo |
| `kind` | `kind` | mantido (`ratio`/`count`/`currency`/`scalar`) |
| `availability` (3 valores) | `state` (**5 valores**) | **ampliado** — ver abaixo |
| `value` | `value` | mantido; `null` em toda ausência |
| `currency` opcional | `currency` **obrigatório** quando há valor monetário | **endurecido** |
| — | `denominator` | **novo** — sem ele a razão não é auditável |
| — | `coverage` | **novo** — só em `partially_measured` |
| descriptor no frontend | `display_precision` no envelope | **movido** para o backend |

### Estados: 3 → 5

| E5 | `analysis-result-v1` |
|---|---|
| `available` | `measured` |
| — | `partially_measured` ← **não existia** |
| `not_measured` | `not_measured` |
| `not_applicable` | `not_applicable` |
| — | `calculation_failed` ← **não existia** |

A E5 não sabia expressar "medido sobre subconjunto" nem "tentou e falhou". Os dois vinham como `not_measured`, e o usuário via a mesma coisa em situações diferentes.

### Ids renomeados

| id da E5 | id público | motivo |
|---|---|---|
| `useful_rate` | `useful_outcome_rate` | "rate" sozinho não diz de quê |
| `intent_coverage_rate` | `intent_coverage_rate` | mantido |
| `cost_per_useful_outcome` | `cost_per_useful_outcome` | mantido |
| `total_cost` | `total_estimated_cost` | é **estimativa**, e o nome precisa dizer |
| **`token_waste_absolute`** | **não existe** | ver abaixo |

## Campo que NÃO tem correspondente

**`token_waste_absolute`, rotulado "Wasted records" na UI, não existe no contrato definitivo.**

O discovery não achou produtor. O produtor real (`estimate_token_cost_waste`) devolve `estimated_wasted_tokens_total` (tokens) e `estimated_token_cost` (moeda) — nenhum é "registros desperdiçados". E a raiz de todos é `int(round(avg_tokens))`, anotada `# proxy` em `core/sentinela_engine.py:1350`.

Não é um campo "ainda não suportado": é um indicador que **nunca teve fato por trás**. Foi classe G (simulado na E5) e sai da UI na migração. A E5 fez a coisa certa ao marcar a massa como PROVISÓRIA — foi isso que permitiu descobrir isto sem quebrar promessa a ninguém.

## O que a UI ganha

1. **Denominador** — "85% sobre 100 conversas analisadas" em vez de "85%".
2. **Dois "coverage" distinguíveis** — `outcome_field_coverage_rate` × `intent_coverage_rate`, que na E5 seriam ambos "coverage".
3. **Parcial visível** — `partially_measured` + `coverage` permitem mostrar "medido sobre metade" em vez de esconder.
4. **Falha de cálculo distinguível de ausência de dado** — mensagens diferentes para situações diferentes.
5. **Precisão vem do backend** — `display_precision` deixa de ser tabela hardcoded no frontend.

## Roteiro sugerido

1. Substituir `provisionalSchema.ts` pelos tipos gerados de `analysis-result-v1`.
2. Estender o mapa de estados de 3 para 5 e escrever os textos dos dois novos.
3. Trocar os ids nos descritores; **remover** `token_waste_absolute`.
4. Exibir denominador e cobertura (ganho novo, não migração).
5. Tornar `currency` obrigatório na formatação monetária.
6. Regenerar as massas de teste a partir de `fixtures/` deste repositório.

Os passos 1–3 mantêm a UI equivalente. Os 4–5 são o ganho. O 6 elimina a última massa provisória do frontend.
