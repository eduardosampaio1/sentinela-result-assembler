# Canonical Result Assembler

> **Assembler organizes facts. Assembler does not calculate analytics.**

Biblioteca Python **pura** que transforma fatos analíticos **já calculados** no resultado público canônico do ARGOS — validado, versionado e determinístico.

```
Engine / domínio analítico
  → analysis-facts-v1      (entrada interna)
  → Result Assembler       ← este repositório
  → analysis-result-v1     (saída pública)
  → Result Store → Gateway → Frontend
```

## O que ele é

O **montador oficial** do resultado. Ele valida fatos, confere cada um contra um registro canônico, organiza seções, declara unidade e denominador, representa disponibilidade e parcialidade, remove o que é interno, e produz um documento estável byte a byte com checksum.

## O que ele não é

Engine · calculadora analítica · frontend · Result Store · Gateway · sistema de recomendação · normalizador de dataset de entrada.

Ele **não pode** calcular score, cobertura, CPUO, desperdício, confiança, drift, volatilidade ou economia; escolher pesos; inferir veredito; criar severidade; priorizar ou eleger recomendação; fabricar data de análise; transformar ausência em zero; substituir métrica por outra parecida; consultar banco, Supabase, LLM, Engine ou MinIO; persistir resultado; expor HTTP.

Formatação pública **não pode mudar significado analítico**: `0.85` sai `0.85`. Virar "85%" é trabalho do frontend.

## Uso

```python
from result_assembler import AnalysisFacts, assemble, serialize_canonical

facts = AnalysisFacts.model_validate(payload)   # recusa campo extra e tipo errado
outcome = assemble(facts)                        # levanta AssemblyError em irregularidade

outcome.public_result       # analysis-result-v1 — seguro para Result Store/Gateway
outcome.internal_manifest   # versões, campos retidos, avisos, checksum
serialize_canonical(outcome.public_result)  # bytes canônicos e estáveis
```

Não há montagem "no melhor esforço": um resultado público montado sobre fato irregular é pior que resultado nenhum, porque parece confiável.

## Garantias

| Garantia | Como é provada |
|---|---|
| **Zero real ≠ ausência** | `state="measured"` com `value=0.0` vs `state="not_measured"` com `value=null` |
| **Cinco estados distintos** de disponibilidade | massa D exercita os cinco num documento só |
| **Razão nunca vira percentual** aqui | `0.85` permanece `0.85`; `kind="ratio"` só autoriza a conversão no consumidor |
| **Contagem nunca vira percentual** | faixa, unidade e precisão contratadas no registro |
| **Precisão preservada** | `0.0042` e `5e-06` sobrevivem à serialização |
| **Data vem do domínio** | cadeado AST proíbe `datetime`/`random`/`os`/`uuid` no pacote |
| **Determinismo** | mesma entrada → mesmos bytes → mesmo checksum, sob permutação |
| **Indicador desconhecido recusa** | fail-closed; sem modo leniente |
| **Nada interno vaza** | varredura por valor + prova estrutural + allowlist de evidências |

## Documentação

| Documento | Conteúdo |
|---|---|
| [ARCHITECTURE](docs/ARCHITECTURE.md) | camadas, fluxo, decisões de desenho |
| [RESPONSIBILITIES](docs/RESPONSIBILITIES.md) | pode / não pode, sem ambiguidade |
| [INDICATOR_REGISTRY](docs/INDICATOR_REGISTRY.md) | os 14 indicadores e os que ficaram de fora |
| [DISCOVERY](docs/DISCOVERY.md) | produtores reais, inventário A–H, armadilhas |
| [PROVENANCE](docs/PROVENANCE.md) | de onde veio cada número das massas |
| [INTEGRATION](docs/INTEGRATION.md) | como ligar ao Orchestrator (ainda não ligado) |
| [SECURITY](docs/SECURITY.md) | o que nunca sai e por quê |
| [E5-MIGRATION](docs/E5-MIGRATION.md) | perfil provisório do frontend → contrato definitivo |
| [DECISIONS](docs/DECISIONS/) | ADRs |

## Desenvolvimento

```bash
pip install -r requirements-dev.txt
```

```bash
PYTHONPATH=src python -m pytest tests/ -q --cov=result_assembler
```

```bash
python -m ruff check src tests scripts && python -m mypy && python scripts/generate_schemas.py
```

Os JSON Schemas em `schemas/` são **derivados** dos modelos tipados. Editá-los à mão não adianta: `tests/test_schemas_e_registro.py` compara com o que o modelo gera e falha se divergirem.

## Estado

Entrega isolada e testável. **Não integrado** a `sentinela`, `sentinela-orchestrator` nem `sentinela-front` — nenhum dos três foi alterado. Sem serviço HTTP, sem persistência, sem deploy.
