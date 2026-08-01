# Arquitetura

## Camadas

```
contracts/     facts.py     analysis-facts-v1  (ENTRADA, interna)
               result.py    analysis-result-v1 (SAÍDA, pública)
               manifest.py  registro técnico da montagem
registry/      indicators.py  o que pode virar indicador público
validation/    invariants.py  20 regras, fail-closed
               safety.py      allowlist de evidência + varredura de conteúdo
assembler/     assemble.py    a montagem (função pura)
serialization/ canonical.py   bytes estáveis + checksum
errors.py                     11 categorias tipadas
version.py                    três eixos de versão, independentes
```

Sem camada cerimonial: cada diretório tem uma responsabilidade que alguém consegue nomear em uma frase.

## Fluxo

```
AnalysisFacts
   │  validate_facts        → versões, identidade, indicadores, recomendações, evidências
   │  validate_evidence_safety → allowlist + conteúdo proibido
   │  dimensões contra SUPPORTED_DIMENSION_IDS (fail-closed)
   ▼
ordem canônica (registro)  ─┐
ordem do domínio (order)   ─┼→ PublicResult
ordem por id (evidências)  ─┘
   │
   ├→ serialize_canonical → checksum
   ▼
AssemblyOutcome(public_result, internal_manifest)
```

## Por que dois contratos e não um

Se entrada e saída compartilhassem o modelo, **todo campo interno novo no domínio vazaria para o público por omissão** — bastaria alguém adicionar um campo ao produtor. Com modelos separados, o vazamento exige que alguém escreva o campo no lado público, e o `test_nenhum_modelo_publico_declara_campo_interno` reprova quando isso acontece por engano.

O custo é uma tradução explícita em `assemble.py`. Vale: é a tradução que dá lugar ao mapeamento de id interno → id público, à seleção de estado e à decisão de o que fica retido.

## Determinismo — as quatro fontes eliminadas

| Fonte | Como foi eliminada |
|---|---|
| Ordem de chegada dos indicadores | publicação segue `CANONICAL_ORDER` do registro |
| Ordem de chaves no JSON | `sort_keys=True` |
| Encoding | `ensure_ascii=False` + UTF-8 explícito |
| Relógio / aleatoriedade / estado global | não existem; cadeado AST proíbe os imports |

Datas necessárias chegam como **fato**. Ordem de recomendação chega como **fato** (`order`). O assembler não tem opinião sobre nenhuma das duas.

## Fail-closed sem modo leniente

Indicador desconhecido, versão desconhecida, unidade divergente, denominador ausente, valor fora da faixa, evidência insegura — todos **recusam a montagem inteira**. Não há flag para "montar assim mesmo".

A consequência de desenho: não existe "indicador excluído" no resultado público. Todo indicador que os fatos trouxeram está publicado; o que varia é o **estado** de cada um. Foi por isso que `Partiality` tem `complete` + `reasons` e não uma lista de exclusões — a lista seria sempre vazia, e campo sempre vazio é campo que mente sobre existir uma possibilidade.

## Estados públicos

| Disponibilidade (fato) | Estado (público) | O que significa |
|---|---|---|
| `available` | `measured` | medido — **zero real mora aqui** |
| `partial` | `partially_measured` | medido sobre subconjunto; `coverage` declara quanto |
| `unavailable` | `not_measured` | entrada ausente ou amostra insuficiente |
| `not_evaluable` | `not_applicable` | os dados existem, a métrica não se aplica |
| `failed` | `calculation_failed` | houve tentativa e erro explícito |

A tabela é um `dict` explícito, não `if` encadeado: um encadeamento é o lugar onde "não medido" vira "zero" numa refatoração distraída.

## Onde a versão de medição fica

`measurement_contract_version` **não** é definida por este pacote. Ela pertence ao domínio analítico, chega nos fatos, é verificada contra `SUPPORTED_MEASUREMENT_CONTRACT_VERSIONS` e é **publicada** no resultado — porque comparar dois resultados de contratos diferentes é um erro que só o consumidor pode evitar, e só consegue se souber.

## Limites assumidos

- **Contagens saem como número JSON** (`100.0`, não `100`). O valor é validado como inteiro; a representação é float por o contrato ter um tipo numérico só. Um tipo união complicaria o schema para ganhar estética.
- **A varredura de conteúdo em evidências é denylist** — rede de proteção, não a defesa. A defesa é a allowlist estrutural de quatro campos.
- **Dimensões não têm registro de unidade/faixa** como os indicadores: hoje são compostos 0..1 do domínio. Quando saírem como fato de verdade, ganham contrato próprio.
