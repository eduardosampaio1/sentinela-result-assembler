# Registro canônico de indicadores

Versão: **`indicator-registry-1.0`** · 14 indicadores.

O registro **não calcula**. Ele responde a uma pergunta só: *este fato pode virar este indicador público, com esta unidade, este denominador e esta faixa?* — e recusa quando não pode.

## Os 14 indicadores

| id interno | **id público** | kind | unidade | denominador | faixa | precisão | origem aceita |
|---|---|---|---|---|---|---|---|
| `useful_rate` | **`useful_outcome_rate`** | ratio | ratio | `analyzed_conversations` | 0..1 | 4 | economics |
| `outcome_coverage` | **`outcome_field_coverage_rate`** | ratio | ratio | `analyzed_conversations` | 0..1 | 4 | economics |
| `conversion_rate` | **`conversion_rate`** | ratio | ratio | `analyzed_conversations` | 0..1 | 4 | economics |
| `intent_coverage_rate` | **`intent_coverage_rate`** | ratio | ratio | `intents` | 0..1 | 4 | tenant |
| `observed_conversations` | **`analyzed_conversation_count`** | count | conversations | — | ≥0 | 0 | economics |
| `useful_outcomes` | **`useful_outcome_count`** | count | conversations | — | ≥0 | 0 | economics |
| `actual_handoffs` | **`handoff_count`** | count | conversations | — | ≥0 | 0 | economics |
| `conversion_count` | **`conversion_count`** | count | conversations | — | ≥0 | 0 | economics |
| `total_estimated_cost` | **`total_estimated_cost`** | currency | ISO-4217 | — | ≥0 | 6 | economics |
| `observed_token_cost_total` | **`token_cost_total`** | currency | ISO-4217 | — | ≥0 | 6 | economics |
| `observed_handoff_cost_total` | **`handoff_cost_total`** | currency | ISO-4217 | — | ≥0 | 6 | economics |
| `cost_per_useful_outcome` | **`cost_per_useful_outcome`** | currency | ISO-4217 | `useful_outcomes` | ≥0 | 6 | economics |
| `cost_per_session` | **`cost_per_session`** | currency | ISO-4217 | `analyzed_conversations` | ≥0 | 6 | tenant |
| `avg_variance_per_intent` | **`mean_response_variance_per_intent`** | scalar | — | — | ≥0 | 4 | tenant |

`economics` = `engine.business.cost_estimators.estimate_useful_outcome_economics`
`tenant` = `engine.business.unit_economics.compute_tenant_metrics`

Todos aceitam `calculation_version` `"1.0"` e os cinco estados de disponibilidade.

## Os três renomeados, e por quê

| interno | público | motivo |
|---|---|---|
| `useful_rate` | `useful_outcome_rate` | "rate" sozinho não diz taxa de quê |
| `outcome_coverage` | `outcome_field_coverage_rate` | mede presença do **campo** `outcome`, não cobertura de intenções — publicar como "coverage" seco é convidar a comparação errada com `intent_coverage_rate` |
| `avg_variance_per_intent` | `mean_response_variance_per_intent` | é **variância**: valor maior significa mais dispersão, não mais qualidade. O nome público impede que vire "consistência" ou "confiança" na leitura |

## O que ficou de fora, e por quê

| candidato | classe | motivo |
|---|---|---|
| **`handoff_rate`** | E | o produtor calcula `1 − useful_rate`. Rodando o código real com 100 conversas / 80 úteis / **zero handoffs**, ele devolve `0.2`. Não é taxa de handoff. Quem quiser handoff usa `handoff_count`, que é **medido** |
| **`token_waste_estimate`** e derivados | H | a raiz é `int(round(avg_tokens))`, anotada `# proxy` no próprio engine. Proxy serve internamente; como indicador público contratado, não |
| **"Wasted records"** (rótulo da E5) | G | **não existe produtor**. O produtor real devolve tokens e moeda, nunca "registros desperdiçados" |
| `global_confidence`, `consistency_score` | H | default `0.0` no contrato torna ausência indistinguível de zero na origem |
| composto `AI_HEALTH` | H | honesto no domínio (`Measurement` com 5 estados), mas ainda não sai como fato. Entra quando o produtor o emitir |

## Dimensões

Quatro ids aceitos — `semantic`, `behavioral`, `structural`, `economic` — os mesmos de `_DIMENSOES_AI_HEALTH` em `core/_engine_helpers.py`. Fail-closed pelo mesmo motivo dos indicadores: dimensão nova exige decisão humana, não passagem automática.

Dimensões passam pela **mesma régua** dos indicadores (versão de cálculo, coerência disponibilidade × valor, faixa 0..1, duplicidade). Não passavam — foi achado do review de semântica.

## Como adicionar um indicador

1. **Prove a semântica no código do produtor.** Fórmula, unidade, denominador, faixa e o que acontece sem dado. Sem isso, ele não entra — foi assim que `handoff_rate` foi barrado.
2. Adicione a entrada em `_DEFINICOES` (`registry/indicators.py`).
3. Adicione o id interno em `CANONICAL_ORDER`, na posição desejada.
4. Rode `python scripts/generate_schemas.py`.
5. Regenere os dourados afetados e olhe o diff.

Os passos 3 e 5 têm gate: `test_ordem_canonica_cobre_exatamente_o_registro` reprova se você esquecer o 3, e o dourado reprova se esquecer o 5. Um indicador registrado fora da ordem canônica nunca seria publicado — e o registro estaria mentindo sobre o que suporta.
