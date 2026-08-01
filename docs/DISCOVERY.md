# Discovery — produtores reais, inventário de fatos e classificação A–H

Inspeção **read-only** de três repositórios, nas baselines congeladas:

| Repositório | Baseline | O que foi lido |
|---|---|---|
| `sentinela` | `e7d0703` | produtores de métrica, `construir_resultado`, contrato de medição, recomendações |
| `sentinela-orchestrator` | `7f02c35` | Result Store, `result_json`, padrão técnico do pacote |
| `sentinela-front` | `bd4d156` (worktree) / `4255932` (original) | perfil provisório da E5, adapters legados |

Nada foi alterado em nenhum dos três.

---

## 1. O gap que justifica este repositório

| Fato medido | Onde |
|---|---|
| O contrato público expõe **`result: unknown`** — nenhum campo analítico contratado | `sentinela/docs/contracts/public-v1.json:28` |
| O Result Store guarda **`result_json jsonb` opaco** | `orchestrator` migration `0009` |
| `construir_resultado` é **um parâmetro injetado sem implementação de produção** | `sentinela/workers/authoritative_engine.py:61,160,207` |
| `"analysis-result-v1"` só existe como **literal de string em testes** — não há schema em repo nenhum | `tests/test_5_5_gate_e2e_publico.py:328` e outros |
| `measurement_contract_version` atravessa Gateway → Orchestrator → Worker → Engine e **nunca recebe valor não-vazio** em código de produção | `infra/gateway_authoritative.py:136`, `workers/authoritative_cycle.py:79` |

O último é o mais instrutivo: o sistema já tinha o **campo** de versionamento, mas não a **prática**. Um campo de versão que nunca é preenchido dá a impressão de contrato versionado sem entregar nenhuma das garantias.

## 2. O que o domínio já faz certo (e este pacote espelha)

`sentinela/core/contracts/measurement.py` tem um contrato de medição **maduro e honesto**:

- **cinco** estados de disponibilidade (`available`, `partial`, `unavailable`, `not_evaluable`, `failed`);
- motivo tipado para máquina (`MeasurementReason`) separado do texto para humano (`limitations`);
- `data_coverage` separado de `confidence` — "quanto do dado entrou" não é "quanto se confia";
- invariantes na construção: `AVAILABLE` exige valor; `UNAVAILABLE`/`NOT_EVALUABLE`/`FAILED` exigem `value is None`; `PARTIAL` exige `0 < coverage < 1`; bool não é medição.

**Decisão**: `analysis-facts-v1` espelha esse vocabulário em vez de inventar outro. O perfil provisório da E5 tinha só três estados e não sabia expressar "medido sobre subconjunto" nem "tentou e falhou".

## 3. Produtores reais de métrica

| Produtor | Arquivo | O que devolve |
|---|---|---|
| `estimate_useful_outcome_economics` | `engine/business/cost_estimators.py:149` | 12 campos de economia observada |
| `compute_tenant_metrics` | `engine/business/unit_economics.py:62` | 7 campos derivados por tenant |
| `estimate_token_cost_waste` | `engine/business/cost_estimators.py:66` | custo e tokens desperdiçados (a partir de um proxy) |
| `build_ai_health_measurement` | `core/_engine_helpers.py:1029` | composto `AI_HEALTH` sobre 4 dimensões |
| `recommendation_ranker` / `output_consolidator` | `engine/recommendations/` | `priority` (P1–P4) + `priority_score` + ordem |
| `materialize_analysis_overview` | `core/materialization/analysis.py:8` | shape do resultado hoje (não contratado) |

## 4. Inventário dos fatos analíticos

Classificação: **A** fato real calculado · **B** metadado real · **C** recomendação do domínio · **D** evidência segura · **E** adaptação legada incorreta · **F** cálculo só no frontend · **G** campo simulado na E5 · **H** sem definição suficiente.

| Fato | Produtor | Campo original | Significado | Tipo | Unidade | Denominador | Faixa | Disponibilidade | Determinístico | Versão | Destino público | Classe |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `useful_rate` | economics | `useful_rate` | úteis ÷ conversas | ratio | ratio | conversas analisadas | 0..1 | 5 estados | sim | 1.0 | `useful_outcome_rate` | **A** |
| `outcome_coverage` | economics | `outcome_coverage` | conversas com campo `outcome` presente ÷ total | ratio | ratio | conversas analisadas | 0..1 | 5 estados | sim | 1.0 | `outcome_field_coverage_rate` | **A** |
| `conversion_rate` | economics | `conversion_rate` | conversões ÷ conversas | ratio | ratio | conversas analisadas | 0..1 | 5 estados | sim | 1.0 | `conversion_rate` | **A** |
| `intent_coverage_rate` | tenant | `intent_coverage_rate` | intenções cobertas ÷ catálogo | ratio | ratio | intenções | 0..1 | 5 estados | sim | 1.0 | `intent_coverage_rate` | **A** |
| `observed_conversations` | economics | idem | conversas consideradas | count | conversations | — | ≥0 | 5 estados | sim | 1.0 | `analyzed_conversation_count` | **A** |
| `useful_outcomes` | economics | idem | conversas com desfecho útil | count | conversations | — | ≥0 | 5 estados | sim | 1.0 | `useful_outcome_count` | **A** |
| `actual_handoffs` | economics | idem | handoffs **medidos** | count | conversations | — | ≥0 | 5 estados | sim | 1.0 | `handoff_count` | **A** |
| `conversion_count` | economics | idem | conversões marcadas | count | conversations | — | ≥0 | 5 estados | sim | 1.0 | `conversion_count` | **A** |
| `total_estimated_cost` | economics | idem | tokens + handoffs | currency | ISO-4217 | — | ≥0 | 5 estados | sim | 1.0 | `total_estimated_cost` | **A** |
| `observed_token_cost_total` | economics | idem | parcela de tokens | currency | ISO-4217 | — | ≥0 | 5 estados | sim | 1.0 | `token_cost_total` | **A** |
| `observed_handoff_cost_total` | economics | idem | parcela de handoffs | currency | ISO-4217 | — | ≥0 | 5 estados | sim | 1.0 | `handoff_cost_total` | **A** |
| `cost_per_useful_outcome` | economics | idem | custo ÷ úteis; **`None` sem úteis** | currency | ISO-4217 | desfechos úteis | ≥0 | 5 estados | sim | 1.0 | `cost_per_useful_outcome` | **A** |
| `cost_per_session` | tenant | idem | custo ÷ conversas | currency | ISO-4217 | conversas analisadas | ≥0 | 5 estados | sim | 1.0 | `cost_per_session` | **A** |
| `avg_variance_per_intent` | tenant | idem | média das variâncias | scalar | — | — | ≥0 | 5 estados | sim | 1.0 | `mean_response_variance_per_intent` | **A** |
| `analyzed_at` | envelope | — | quando a análise rodou | metadado | ISO-8601 | — | — | obrigatório | sim | — | `summary.analyzed_at` | **B** |
| `record_count` | envelope | — | registros considerados | metadado | count | — | ≥0 | obrigatório | sim | — | `summary.record_count` | **B** |
| `engine_version` / `dataset_fingerprint` | provenance | — | proveniência técnica | metadado | — | — | — | — | sim | — | **só manifesto** | **B** |
| recomendações | ranker | `id/title/priority/order` | ação já priorizada | — | — | — | — | — | sim | — | `recommendations[]` | **C** |
| evidências | domínio | `id/kind/observed_count/label` | resumo agregado | — | — | — | — | — | sim | — | `evidence[]` | **D** |
| **`handoff_rate`** | tenant | `handoff_rate` | **`1 − useful_rate`** | — | — | — | — | — | — | — | **NÃO ENTRA** | **E** |
| `cost_per_useful_outcome` colapsado | adapter legado | `_as_float(..., 0.0)` | `None` virando `0.0` | — | — | — | — | — | — | — | **NÃO ENTRA** | **E** |
| conversão "85%" | frontend | — | `ratio × 100` | — | — | — | — | — | — | — | **fica no frontend** | **F** |
| **"Wasted records" = 20** | — | — | **não existe produtor** | — | — | — | — | — | — | — | **NÃO ENTRA** | **G** |
| `analyzed_at` da E5 | fixture E5 | — | simulado | — | — | — | — | — | — | — | **NÃO ENTRA como fato** | **G** |
| `token_waste_estimate` | engine | `int(round(avg_tokens))` | **proxy** (anotado no código) | — | — | — | — | — | — | — | **NÃO ENTRA** | **H** |
| `global_confidence` / `consistency_score` | contracts | default `0.0` | ausência indistinguível de zero | — | — | — | — | — | — | — | **NÃO ENTRA** | **H** |
| composto `AI_HEALTH` | `_engine_helpers` | `Measurement` | honesto, mas não chega como fato | — | — | — | — | 5 estados | sim | — | dimensões (quando emitido) | **H** |

**14 fatos classe A entraram no registro.** Nenhum campo E, F, G ou H entrou.

## 5. As três armadilhas semânticas, com a evidência

### 5.1 `handoff_rate` não é taxa de handoff

```python
# engine/business/unit_economics.py
handoff_rate = (1.0 - useful_rate) if useful_rate > 0 else 0.0
```

Rodando o produtor real com 100 conversas, 80 úteis e **zero handoffs**, o resultado é `handoff_rate: 0.2` — e `actual_handoffs: 0` no mesmo snapshot. O campo mede o complemento de outra métrica e leva o nome de uma terceira coisa. **Fora do registro**; quem quiser handoff usa `handoff_count`, que é medido.

### 5.2 "coverage" é duas coisas diferentes

Na massa A, `outcome_coverage` e `intent_coverage_rate` valem **os dois 0.85**, medidos de verdade, por produtores diferentes, sobre denominadores diferentes (conversas × intenções). Publicar qualquer um deles como "coverage" seco é convidar a comparação errada. Os nomes públicos são explícitos, e o denominador viaja junto.

### 5.3 "Wasted records" da E5 não tem produtor

O perfil provisório da E5 rotulava `token_waste_absolute: 20` como **"Wasted records"**. O produtor real (`estimate_token_cost_waste`) devolve `estimated_wasted_tokens_total` (tokens) e `estimated_token_cost` (moeda) — nenhum dos dois é "registros desperdiçados". E a raiz de todos é `int(round(avg_tokens))`, anotado `# proxy` em `core/sentinela_engine.py:1350`. **Nenhuma variante entrou.**

## 6. Lacunas que a integração precisa fechar

| # | Lacuna | Consequência hoje |
|---|---|---|
| L1 | Nenhum produtor emite `analysis-facts-v1` | O assembler está pronto e sem produtor — a fiação é a próxima etapa |
| L2 | `calculation_version` não existe no domínio | O contrato exige; o produtor precisará declarar |
| L3 | `measurement_contract_version` nunca é preenchido | Precisa passar a valer `measurement-1.0` |
| L4 | Nenhum produtor emite código ISO de moeda | Os campos se chamam `*_usd`; o código precisa ser explícito |
| L5 | `construir_resultado` não tem implementação de produção | É exatamente o ponto onde o assembler entra |
| L6 | O composto `AI_HEALTH` não sai como fato | Dimensões ficam vazias até isso mudar |
