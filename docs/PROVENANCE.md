# Proveniência das massas

Nenhum número destas fixtures foi inventado. Todos vieram de **executar o código analítico real** do repositório `sentinela` @ `e7d0703`, localmente, em modo leitura, e depois sanitizar para fixture.

**Funções executadas**
- `engine/business/cost_estimators.py::estimate_useful_outcome_economics`
- `engine/business/unit_economics.py::compute_tenant_metrics`

**Sanitização aplicada a todas**: nenhum dado real de cliente; ids sintéticos (`an-massa-*`); `engine_version` é rótulo da baseline lida, não build real.

---

## Massa A — principal

**Entrada**: 100 registros, cada um com `trace.estimated_cost_usd = 0.10`; 85 com campo `outcome` presente; 80 com `outcome.useful = true`; nenhum handoff; nenhuma marca de conversão.

**Saída medida** (`estimate_useful_outcome_economics`):

```
observed_conversations 100 | outcome_coverage 0.85 | useful_outcomes 80
useful_rate 0.8 | actual_handoffs 0 | observed_token_cost_total 10.0
observed_handoff_cost_total 0.0 | total_estimated_cost 10.0
cost_per_useful_outcome 0.125
```

**Saída medida** (`compute_tenant_metrics`, com `covered_intents=17`, `total_intents=20`):

```
cost_per_session 0.1 | intent_coverage_rate 0.85
```

**Conferência manual**: 80 ÷ 100 = 0.8 ✓ · 85 ÷ 100 = 0.85 ✓ · 17 ÷ 20 = 0.85 ✓ · 100 × 0.10 = 10.00 ✓ · 10.00 ÷ 80 = **0.125** ✓ · 10.00 ÷ 100 = 0.1 ✓

**Determinísticos**: os 11 indicadores. **Simulado**: `currency: "USD"` — o produtor **não emite código ISO**; USD é derivado do nome do próprio campo dele (`trace.estimated_cost_usd`). A exigência do contrato é a lacuna **L4** do discovery.

**Detalhe de desenho**: a massa foi montada **sem handoff** de propósito. Com handoff, o default `handoff_cost_per_case=12.0` inflaria o custo e o total não bateria 10.00 redondo.

**O que a massa A também prova**: `outcome_coverage` e `intent_coverage_rate` valem **os dois 0.85**, medidos por produtores diferentes sobre denominadores diferentes. É a demonstração viva de por que "coverage" seco é ambíguo.

**Não entrou na massa A**: `conversion_rate`/`conversion_count` (os registros não têm campo de conversão — o produtor conta 0, mas isso é ausência de dado, não conversão zero) e `avg_variance_per_intent` (sem itens de variância o produtor devolve `0.0` no `else`, que é **absence-as-zero na origem**). Publicá-los como zero medido seria repetir o defeito que este pacote existe para impedir.

---

## Massa B — zero real × não medido

**Entrada**: 10 registros a `0.05`; **nenhum** com campo `outcome`.

**Saída medida**:

```
observed_conversations 10 | outcome_coverage 0.0 | useful_outcomes 0
useful_rate 0.0 | total_estimated_cost 0.5 | cost_per_useful_outcome None
```

O par crítico: `outcome_coverage 0.0` é **zero real** (o produtor mediu e não achou nenhum) e `cost_per_useful_outcome` é **`None`** (não há como dividir por zero úteis). Na fixture, o primeiro é `available` e o segundo é `unavailable`/`no_input_data`.

É exatamente aqui que `core/adapters/argos.py` erra hoje: `_as_float(snapshot.get("cost_per_useful_outcome"), 0.0)` colapsa o `None` em `0.0`, e os dois viram a mesma coisa.

**Determinísticos**: todos. **Simulado**: `currency`.

---

## Massa C — sub-centavo

**Entrada**: 1000 registros a `0.0000042`; 800 úteis.

**Saída medida**:

```
total_estimated_cost 0.0042 | cost_per_useful_outcome 5e-06
```

Prova que `0.0042` não vira `0.00` e que `5e-06` sobrevive à serialização canônica.

**Determinísticos**: os 4. **Simulado**: `currency`.

---

## Massa D — parcialidade (os cinco estados)

**Construída**, não medida — o objetivo é exercitar os cinco estados num documento só, e nenhuma execução real produz os cinco de uma vez.

| indicador | estado | por quê |
|---|---|---|
| `useful_rate` 0.6 | `available` | medido |
| `intent_coverage_rate` 0.4 | `partial` | cobertura 0.5, 25 de 50 intenções |
| `cost_per_useful_outcome` | `unavailable` | `insufficient_sample` |
| `conversion_rate` | `not_evaluable` | `not_applicable` |
| `avg_variance_per_intent` | `failed` | `computation_error` |

Mais duas dimensões (`economic` available, `semantic` partial).

**Determinísticos**: nenhum valor aqui é medição real. **Toda a massa D é construída** — declarado aqui para que ninguém a cite como evidência empírica. Ela prova **comportamento do assembler**, não fato do domínio.

Os contadores `observed_units=25` / `expected_units=50` são coerentes com `data_coverage=0.5` — coerência que virou invariante depois do review de semântica.

---

## Massa E — versão incompatível

`measurement_contract_version: "measurement-9.9"`. **Construída.** Existe para provar a recusa: `UnsupportedMeasurementVersion`, nunca um resultado montado.

---

## Massa F — recomendações e evidências

**Construída.** Três recomendações chegando **fora de ordem** no payload (`rec-c`, `rec-a`, `rec-b`) com `order` 2, 0, 1 e prioridades P3, P1, P2. Duas evidências fora de ordem por id.

Prova que a publicação segue `order` (do domínio) e não a ordem da lista, e que evidências saem ordenadas por id.

Os textos (`"Cobrir intencoes sem amostra"`) são **simulados** — não vieram do `recommendation_ranker`. O que a massa prova é **transporte e ordem**, não conteúdo de recomendação.

---

## Resumo: determinístico × simulado

| Massa | Valores numéricos | `currency` | `analyzed_at` | Textos | Estados |
|---|---|---|---|---|---|
| A | **medidos** | simulado (derivado do nome do campo) | simulado | — | medidos |
| B | **medidos** | simulado | simulado | — | medidos |
| C | **medidos** | simulado | simulado | — | medidos |
| D | construídos | simulado | simulado | — | construídos |
| E | construídos | — | simulado | — | — |
| F | 1 medido (0.8) | — | simulado | simulados | medido |

`analyzed_at` é simulado em **todas**: as execuções locais não geram timestamp de análise. Isso não enfraquece nada — o ponto do campo é que ele **vem de fora**, e a fixture o fornece de fora.
