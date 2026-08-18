# `analysis-result-v3` — contrato público do ARGOS

> **Autoridade:** decisões de owner de 2026-08-12 (ARGOS Publication Recovery).
> **Estado:** especificação congelada. A implementação vem nas ondas R1–R8.
> **Escopo:** ARGOS e só ARGOS. O Analytics tem contrato próprio e não entra aqui.

---

## 1. Por que existe uma v3

O discovery mediu: das **34** métricas do documento *"Métricas do Sentinela ARGOS"*, **8**
chegavam ao contrato público. As outras não foram recusadas — elas não estavam na tabela de
14 ids de `engine/facts/producer.py`, e nada no sistema comparava o que o motor produz com o
que o produto publica.

Três contratos, três destinos:

| contrato | conteúdo | estado |
|---|---|---|
| `analysis-result-v1` | Engine facts (14 indicadores) | **mantido**, imutável. `additionalProperties: false` em 8 pontos — **não cresce** |
| `analysis-result-v2` | Engine facts **+** projeção Analytics | **congelado como legado compatível**. Não é ampliado semanticamente |
| `analysis-result-v3` | **ARGOS completo, só ARGOS** | **novo** |

O v1 não pode crescer por construção. O v2 funde os dois motores, o que contraria a
arquitetura de dois motores independentes. Logo o primeiro contrato coerente é o v3.

---

## 2. Aritmética do catálogo — o gate zero

**34 documentadas + 5 descobertas = 39 outputs quantitativos.**

| família | n |
|---|---|
| `scores[]` | 7 |
| `dimensions[]` | 4 |
| `indicators[]` | 18 |
| `intents[]` | 1 |
| `risks[]` | 2 |
| `projections[]` | 4 |
| `method.method_parameters` | 1 |
| **bloqueados** | **2** |
| **total** | **39** |

**37 publicáveis + 2 bloqueados = 39.** A lista nominal é
`result_assembler/registry/argos_catalog.py`; o gate é `tests/test_catalogo_argos.py`.

### 2.1 A regra da família única

Cada output mora em **exatamente uma** família, e o `public_id` é único no catálogo inteiro.
A primeira versão desta spec falhou aqui: publicava `Response Variance` como score global
**e** como `mean_response_variance_per_intent` em indicadores — a mesma métrica em duas
roupas, inflando a contagem para 40. O gate reprova por unicidade de `public_id`.

`Response Variance` é **um** output, e vive em `indicators[]`. O detalhe por intenção mora em
`intents[]` como grão fino da mesma métrica, não como entrada nova do catálogo. Vale o mesmo
para `Response Stability`.

---

## 3. `PublicMeasurement` — o envelope canônico

Projeção pública de `core.contracts.measurement.Measurement`. Carrega **valor separado de
disponibilidade** — é a peça que impede ausência virar zero, e é o que destrava
`consistency_score` e `global_confidence`, excluídos do v1 exatamente por isso.

```
PublicMeasurement
  id              string
  value           number | null
  availability    "measured" | "partially_measured" | "not_measured"
                  | "not_applicable" | "calculation_failed"
  reason          "ok" | "no_input_data" | "insufficient_sample" | "single_group"
                  | "missing_dimension" | "dependency_unavailable"
                  | "not_applicable" | "computation_error"
  data_coverage   number | null        // 0..1
  confidence      number | null        // 0..1 — desta medição, NÃO `global_confidence`
  scale           Scale
  thresholds      PublicThresholds | null
  method_version  string | null        // obrigatório onde a fórmula pode mudar
  domain          "semantic" | "behavioral" | "structural" | "economic" | null
  unit            string | null        // onde a escala não determina (duration, currency)

Scale
  kind            "ratio_unit" | "score_100" | "percent" | "currency"
                  | "count" | "duration" | "raw"
  minimum         number | null        // DECLARATIVO: a régua, não o cadeado
  maximum         number | null

PublicThresholds
  warn            number
  critical        number
```

O bloco acima é travado por gate contra os modelos reais
(`test_spec_e_derivada_do_modelo`). Antes do gate ele havia derivado três vezes: listava um
`evidence_level` que não existe, chamava os campos da `Scale` de `min`/`max`, e não citava o
`confidence` que a D5 introduziu.

### 3.1 Invariantes

1. `availability = measured` ⇒ `value != null`
2. `availability ∈ {not_measured, not_applicable, calculation_failed}` ⇒ `value = null`
3. `availability = partially_measured` ⇒ `value != null` **e** `data_coverage < 1`
4. `reason = "ok"` ⇔ `availability ∈ {measured, partially_measured}`
5. `value` fora da **faixa canônica do `scale.kind`** é erro de montagem —
   `ratio_unit` = 0..1, `score_100` e `percent` = 0..100. As demais têm faixa **aberta** e o
   invariante não morde nelas.

   **`scale.minimum`/`maximum` NÃO são o cadeado.** Eles declaram a régua para quem lê; a
   validação usa a faixa canônica do `kind`. A redação anterior deste item dizia
   *"`value` fora de `[scale.min, scale.max]`"* — e essa frase custou um desenho errado:
   a fatia do limiar começou gravando os cortes `75/60` em `minimum`/`maximum` supondo que
   ali houvesse restrição, quando o efeito real seria a tela escrever `60–75` como a régua de
   um número que vive em 0..100.
6. `thresholds`, quando presente: cortes finitos, **distintos**, e dentro da faixa canônica do
   `kind`. Um corte fora da régua deixaria a zona inalcançável.

### 3.2 `reason` atravessa a fronteira

**Decisão do owner: publicar.** `reason` é vocabulário público fechado de disponibilidade,
não detalhe de implementação.

O argumento é medido: com a moeda ausente, os cinco monetários saem `not_measured`. Sem
`reason`, o consumidor lê "não medido" e não tem o que dizer nem o que fazer. Com
`dependency_unavailable`, a tela informa *"custo indisponível: moeda não declarada"*.

`source` técnico (`engine.business.…`) **continua retido** — ele revela implementação e não
acrescenta nada ao consumidor. `domain` cobre a necessidade legítima de procedência
semântica sem expor internals.

### 3.3 Escala é contrato

Toda medição declara `scale`. **Nenhuma conversão silenciosa em nenhuma camada.**

`response_stability` é produzido em **0..100** (`100 * (1 - variance)`) e **é publicado em
0..100**, com `scale.kind = "score_100"`. Dividir por 100 no bridge seria normalização
numérica não autorizada — a mudança de escala é decisão metodológica do produtor, não da
publicação.

### 3.4 Limiar é campo próprio, e a ordem carrega a direção

A **escala** é a régua; o **limiar** são os cortes nela. São campos diferentes porque
respondem perguntas diferentes — *"em que régua este número vive"* e *"onde começa o ruim"* —
e porque o consumidor já renderiza `minimum`/`maximum` como a régua.

`critical < warn` significa **menor é pior**: a zona ok fica acima de `warn`.
`critical > warn` significa **maior é pior**, e a zona ok fica abaixo. Não há campo de
orientação: a direção é função total da ordem, e um campo afirmando o que a ordem já diz seria
segunda cópia do mesmo fato — com um validador para reconciliá-las, que é o arranjo que a
Regra 14 existe para impedir. O precedente de `scale.kind` (*"declarada, nunca inferida"*) não
se aplica: escala **não** é derivável do dado (`0.8` não diz se a régua é 0..1 ou 0..100);
direção é.

**Quem tem limiar.** O motor aplica um par — `THR_WARN = 75`, `THR_CRIT = 60` — a duas saídas:
`intent_score` (que publica o `governance_score`, exatamente o número julgado em
`_sentinela_governance.py:153`) e `behavior_score`. Nas outras o campo sai `null`, e isso é
honesto: aplicar `75/60` a um custo em dólar ou a uma taxa de conversão seria inventar
semântica que ninguém mediu. Quem decide o "bom" das outras é produto.

**Por que `behavior_score` recebe o mesmo par.** Ele é `max(0, raw_governance_score −
cross_intent_penalty)` **sem** o fator de confiança amostral, por decisão de owner da D5. Os
limiares foram aplicados historicamente ao número **com** o fator. Medido antes de publicar:
varredura de `raw × penalidade`, 101×101 = **10.201 pontos**, com amostra cheia
(`n ≥ CONF_FULL_AT_N = 10`) → **zero** pontos de divergência, porque em `conf = 1` as duas
fórmulas são idênticas. A divergência é exclusivamente efeito de amostra curta — que é o que a
D5 tirou do valor e passou a reportar ao lado, em `confidence`. Consequência declarada: na
faixa `n ∈ [5, 9]` — do piso de cobertura à confiança cheia — o alarme deixa de disparar por
evidência fina, de propósito.

**Limiar não depende de valor.** Ele é propriedade da métrica, não da medição. Medição ausente
com limiar publicado é o caso útil: a tela sabe onde ficaria o bom e desenha o vão com as
zonas, em vez de um traço sem referência.

**Limiar nunca altera `value`.** Mesma regra de `confidence`. Uma camada que "ajustasse" o
valor para dentro da zona estaria produzindo métrica.

---

## 4. Estrutura do documento

```
analysis-result-v3
├── analysis_id                    string
├── result_schema_version          "analysis-result-v3"
├── indicator_registry_version     string
├── measurement_contract_version   string
├── argos_catalog_version          string
├── summary                        Summary
├── method                         MethodMetadata
├── partiality                     Partiality
├── scores[]                       PublicMeasurement
├── dimensions[]                   PublicMeasurement
├── indicators[]                   PublicIndicator
├── intents[]                      IntentEntry
├── risks[]                        RiskEntry
├── projections[]                  ProjectionEntry
├── recommendations[]              PublicRecommendation
├── evidence[]                     PublicEvidenceSummary
├── alerts[]                       AlertEntry
├── issues[]                       IssueEntry
└── executive_summary              ExecutiveSummary | null
```

`additionalProperties: false` também no v3. A rigidez do v1 é o que fez o defeito aparecer em
vez de passar calado; ela se mantém.

### 4.1 Omitido × vazio — regra obrigatória

| forma | significado |
|---|---|
| campo/família **omitida** | a capacidade/produtor **não existe** neste documento |
| `[]` | a capacidade existe, foi executada e produziu **zero itens** |

Nunca usar `[]` como substituto de "não implementado". Foi assim que `evidence: []` — fixo no
producer, sem produtor algum por trás — passou como se fosse resposta.

### 4.2 `summary` e `method`

```
Summary
  analyzed_at   string   // ISO-8601 UTC
  record_count  number

MethodMetadata
  method_parameters   { min_samples_per_intent: number, ... }
  currency            string | null    // ISO-4217
  currency_source     "dataset_mapping" | "analysis_snapshot" | null
```

`summary` **não** carrega texto: o resumo executivo tem bloco próprio, com idioma.

<!-- GERADO: tabela de escalas — não editar à mão -->

> Derivada de `_ESCALA_POR_SAIDA` e do catálogo ARGOS por
> `scripts/gerar_tabela_de_escalas.py`. O **código é canônico**: a escala é decisão do
> PRODUTOR, e uma tabela escrita à mão já divergiu dele uma vez sem ninguém ver.

### `scores[]` — 7 entradas

| public_id | escala | nota |
|---|---|---|
| `behavior_score` | `score_100` | escore global; exige method_version para ser comparável |
| `ai_health_score` | `ratio_unit` | composto das 4 dimensões — NÃO é a quinta dimensão |
| `consistency_score` | `score_100` | excluído no v1 por absence-as-zero; o envelope Measurement resolve |
| `global_confidence` | `ratio_unit` | confiança sobre a análise, não sobre o negócio |
| `cross_intent_similarity` | `ratio_unit` |  |
| `response_stability` | `score_100` | escala 0..100 do produtor, publicada como tal (D5 do owner); converter no bridge seria normalização não autorizada |
| `semantic_drift` | `ratio_unit` | medido DENTRO de uma análise; não é delta A×B da EVO-02 |

### `risks[]`

| public_id | escala | nota |
|---|---|---|
| `containment_risk` | `ratio_unit` |  |
| `conversion_risk` | `ratio_unit` |  |

### `projections[]`

| public_id | escala | nota |
|---|---|---|
| `projected_token_cost@month` | **sem escala declarada** | horizonte é DADO; o `@` só desambigua a identidade no catálogo |
| `projected_token_cost@year` | **sem escala declarada** |  |
| `projected_handoff_cost@month` | **sem escala declarada** |  |
| `projected_handoff_cost@year` | **sem escala declarada** |  |

### `intents[]`

| public_id | escala | nota |
|---|---|---|
| `intent_score` | `score_100` | por intenção, com suporte amostral e severidade; achatar em indicators[] perderia a identidade da intenção |

<!-- FIM DO GERADO -->

`ai_health_score` declara `composite_of: ["semantic","behavioral","structural","economic"]`.
**Não é a quinta dimensão** — colocá-lo em `dimensions[]` faria qualquer agregação somar o
composto junto das partes.

`semantic_drift` carrega `method_window`. Ele é medido **dentro de uma análise**; não é delta
A×B, e não tem relação com a comparação da EVO-02.

### 4.4 `dimensions[]` — as quatro

`semantic` · `behavioral` · `structural` · `economic`

O motor produz `semantic_health` etc. em `argos_v2["measurements"]`. **A normalização
nominal acontece na fronteira de publicação**, sem recalcular valor. O motor não muda
vocabulário interno por causa de contrato público.

### 4.5 `indicators[]` — 18 entradas

Métrica de negócio escalar, com unidade e denominador. Mantém a forma do v1 e **ganha**
`reason`, `scale` e `domain`.

Os 14 atuais + `estimated_handoff_cost`, `intents_detected_count`, `covered_intents_count`,
`critical_alert_count`.

`critical_alert_count` é a **contagem**; o conteúdo dos alertas vive em `alerts[]`. Métrica e
saída analítica não se misturam.

### 4.6 `intents[]`

O ARGOS **já produz** esta estrutura (`core/_engine_helpers.py:88`).

```
IntentEntry
  intent_id            string
  score                PublicMeasurement
  support              number              // n_conversations
  severity             "ok" | "warning" | "critical"
  underrepresented     boolean             // support < min_samples_per_intent
  response_variance    PublicMeasurement | null
  response_stability   PublicMeasurement | null
```

`underrepresented` é derivado de dado publicado, não de juízo — e produz a lista de intenções
sub-representadas sem uma segunda estrutura.

### 4.7 `risks[]`

```
RiskEntry
  id            "containment_risk" | "conversion_risk"
  measurement   PublicMeasurement
  band          "low" | "moderate" | "high" | null
```

**`band` só é publicada quando o produtor a fornece.** Nenhuma camada intermediária a
calcula, e o consumidor nunca deriva limiar a partir de `0..1` — seria inventar decisão de
produto na apresentação. Sem produtor: `band` ausente.

### 4.8 `projections[]`

Horizonte é **dado**, não sufixo de nome.

```
ProjectionEntry
  id            "projected_token_cost" | "projected_handoff_cost"
  horizon       "month" | "year"
  measurement   PublicMeasurement       // scale.kind = "currency"
  currency      string | null
  basis         string
```

### 4.9 Famílias analíticas

A forma nasce no v3; a implementação pode ser onda posterior. Enquanto não houver produtor,
o campo é **omitido** (§4.1).

```
PublicRecommendation   id, title, priority, category, evidence_refs[], order
PublicEvidenceSummary  id, kind, label, observed_count
AlertEntry             id, severity, code, title, detail, evidence_refs[], affected_intents[]
IssueEntry             id, severity, code, title, evidence_refs[]
ExecutiveSummary       language (BCP-47), text, generated_by
```

---

## 5. Outputs bloqueados

| output | estado | motivo |
|---|---|---|
| `token_waste` | `BLOCKED_BY_MEASUREMENT_SEMANTICS` | o produtor mede `int(round(avg_tokens))`, anotado `# proxy`. O nome promete desperdício; a medida não o entrega |
| `token_waste_cost` | `BLOCKED_BY_MEASUREMENT_SEMANTICS` | deriva do acima |

**Não são mascarados como `not_measured`.** `not_measured` diz *"tentamos medir e não deu"*;
bloqueado é *"o produto decidiu não publicar"*. São coisas diferentes e o consumidor precisa
distinguí-las. Bloqueado **não aparece** no documento.

O envelope `Measurement` resolve *ausência representada como zero*. Não resolve *métrica
semanticamente errada* — e é por isso que estes dois continuam fora. Corrigir a fórmula exige
nova decisão do owner.

---

## 6. Currency — cadeia de propriedade

```
dataset/mapping  ──declara a moeda dos campos monetários──►  mapping (+ currency)
      │
      ▼  ao preparar a Analysis, vira SNAPSHOT durável e imutável
  Analysis.currency
      │
      ▼  atravessa a cadeia real
  engine_api ──► facts_do_resultado_do_engine(currency=<da Analysis>)
      │
      ▼
  producer: kind == "currency" e sem moeda
            ⇒ not_measured / dependency_unavailable
```

A moeda descreve o significado do custo **na fonte de dados**, não no Workspace: o mesmo
workspace pode analisar datasets em moedas diferentes.

O Engine **consome** moeda; não a inventa. Sem moeda declarada, os cinco monetários saem
`not_measured` + `dependency_unavailable`. **Nunca inferir USD** — nem do nome do campo
(`estimated_cost_usd`), que é de onde a fixture tirou a sua.

### 6.1 Estado da implementação (R1-currency)

| peça | onde | estado |
|---|---|---|
| id canônico reservado + ISO-4217 obrigatório | `ingestion_service/contracts/regra_de_medida.py` | ✅ |
| leitura canônica, batch e streaming | `engine/business/cost_input.py` | ✅ |
| moeda viaja com o valor até o fato | `engine/facts/from_engine_result.py::extrair_moeda` | ✅ |
| motivo (`no_input_data` × `dependency_unavailable`) atravessa | `producer.py::_indicador` | ✅ |
| extrator legado neutralizado + gate por AST | `_extract_trace_cost_LEGADO` | ✅ |

**Um leitor monetário por nome de campo ainda existe** e precisa da mesma canonização:
`impact_model.py::explicit_handoff_cost` lê `outcome.handoff_cost_usd` /
`observed_handoff_cost_usd`. Ele é o **custo unitário observado de um handoff** — per-record,
como o custo da conversa —, e a saída natural é um segundo id reservado (`handoff_cost`),
seguindo o mesmo padrão. Não foi feito em R1-currency: é escopo além do custo por conversa, e
exige decisão sobre como declarar um custo que só existe nos registros que tiveram handoff.

> **Anotação de arqueologia.** Ao separar as fontes, apareceu um `payload` de `impact_model`
> com **seis chaves duplicadas no mesmo literal** — atribuídas de `observed_metrics` e
> reatribuídas de `unit_economics` logo abaixo. Python fica com a última, então metade era
> código morto desde sempre. Passou despercebido porque as duas fontes davam o mesmo número
> por coincidência aritmética (`12.0 × 6 handoffs = 72.0`). As mortas foram removidas
> preservando a fonte viva — apagar código morto não é escolher significado novo.

---

## 7. Versionamento e compatibilidade

`AnalysisResultView.result_schema_version` **já existe** e é o discriminador. Nenhum campo
novo é necessário no envelope para negociar.

1. Uma análise é montada em **uma** versão, que fica gravada com o resultado.
2. O cliente lê `result_schema_version` **antes** de interpretar o documento.
3. Nenhuma conversão implícita no Gateway. Documento montado como v1 continua v1.
4. Clientes que só conhecem v1 seguem funcionando: nada já persistido é reescrito.
5. Quem não reconhece a versão **recusa explicitamente**, nunca adivinha.

---

## 8. Gates obrigatórios

| # | gate | o defeito que ele teria pego |
|---|---|---|
| G1 | **Catálogo nominal** — 39, família única, sem alias | as 21 ausências silenciosas e os 5 extras fora do catálogo |
| G2 | **Engine → publication completeness** — todo output autorizado vira fato ou tem bloqueio testado | o desaparecimento silencioso |
| G3 | **Fixture representativa** — "resposta literal da API" percorre o caminho real, com os mesmos argumentos do chamador de produção | `currency="USD"` no teste × `None` na produção |
| G4 | **Currency** — sem moeda ⇒ monetários `not_measured`/`dependency_unavailable`; com moeda ⇒ valores | o defeito medido na Fase E |
| G5 | **Health** — `*_health` → normalização → `dimensions[]`, com **teste negativo**: ligar o fio sem normalizar deve reprovar | `dimensions: []` que passaria por conserto |
| G6 | **Absence ≠ zero** — `availability != measured` ⇒ `value = null` | o motivo original das exclusões |
| G7 | **Provenance fail-closed** — `source` não autorizada reprova na montagem | mantido do v1 |
| G8 | **Escala** — toda medição declara `scale`; valor fora da faixa reprova; nenhuma conversão fora do ponto declarado | `score_100` virar `ratio_unit` em silêncio |
| G9 | **Omitido × vazio** — família sem produtor é omitida, nunca `[]` | `evidence: []` fixo |

---

## 9. Ondas

| onda | conteúdo |
|---|---|
| **R0** | esta spec + catálogo em código + G1 |
| **R1** | fixture real · cadeia de currency · wiring de health + normalização nominal |
| **R2** | schema v3, tipos, `PublicMeasurement`, famílias estruturais |
| **R3** | pipeline de publicação ponta a ponta |
| **R4** | famílias analíticas, conforme produtores reais |
| **R5** | contrato publicado em `sentinela-facts/docs/contracts` |
| **R6** | provas reais na cadeia local |
| **R7** | compatibilidade v1/v2/v3 |
| **R8** | DOC-CLOSE e freeze |
