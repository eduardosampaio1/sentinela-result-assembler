# Responsabilidades

> Assembler organizes facts. Assembler does not calculate analytics.

## Pode

| Pode | Onde |
|---|---|
| validar fatos | `validation/invariants.py` |
| validar versões (facts, medição, cálculo) | `validation/invariants.py` |
| mapear id interno aprovado → id público | `registry/indicators.py` |
| organizar seções | `assembler/assemble.py` |
| ordenar pela ordem **contratada** (registro) ou **recebida** (`order` do domínio) | `assembler/assemble.py` |
| declarar unidade | registro; conferida contra o fato |
| declarar denominador | registro; conferido contra o fato |
| representar disponibilidade | tabela explícita `Availability → IndicatorState` |
| representar parcialidade | `Partiality` (`complete` + `reasons`) |
| aplicar `result_schema_version` | `version.py` |
| remover campos não públicos | modelos separados + `withheld_internal_fields` |
| construir envelope | `PublicResult` |
| produzir JSON canônico | `serialization/canonical.py` |
| produzir manifesto interno | `contracts/manifest.py` |
| calcular checksum **técnico do documento** | `serialization/canonical.py` |
| rejeitar contradições | fail-closed em toda a validação |

O checksum é a única coisa que o assembler "calcula" — e é sobre **bytes**, não sobre analítica. É o hash do documento montado, não uma métrica.

## Não pode

**Calcular**: behavior score · coverage · CPUO · token waste · confidence · drift · volatilidade · economia.

**Decidir**: escolher pesos · inferir verdict · criar severidade · priorizar recomendações · escolher a recomendação principal.

**Fabricar**: data de análise · valor onde não houve medição · métrica parecida no lugar de outra.

**Transformar**: ausência em zero · contagem em percentual · razão em percentual.

**Acessar**: banco · Supabase · LLM · Engine · MinIO · filesystem compartilhado · fila · rede.

**Persistir** ou **expor HTTP** — nesta primeira entrega.

## A regra que resume

**Formatação pública não pode mudar significado analítico.**

`0.85` sai `0.85`. O consumidor com `kind="ratio"` sabe que pode mostrar "85%". Se o assembler multiplicasse por 100, o frontend multiplicaria de novo e sairia **8.500%** — que foi exatamente o defeito que o discovery do frontend encontrou.

`display_precision` é **sugestão**. O valor sai como o domínio calculou: `0.0042` chega íntegro, e quem exibe decide se mostra `0.0042` ou `< 0.01`.

## Como cada proibição é provada

| Proibição | Prova |
|---|---|
| não calcula analítica | registro não tem fórmula; `assemble.py` não tem operação aritmética sobre valores |
| não fabrica data | cadeado AST proíbe `datetime`/`time`/`uuid`/`random`/`os`/`secrets` no pacote; mutação m3 morre |
| ausência não vira zero | invariante dedicado + massa B + mutação m10 |
| contagem não vira percentual | faixa/unidade/precisão contratadas + mutação m1 |
| não reordena recomendação | ordem vem de `order`; mutação m6 morre |
| não elege principal | nenhum campo do contrato público permite marcar principal — teste estrutural |
| não acessa rede/banco | `requirements.txt` tem **uma** dependência (pydantic); cadeado AST |
| nada interno vaza | varredura por valor + prova estrutural + allowlist de evidência |
