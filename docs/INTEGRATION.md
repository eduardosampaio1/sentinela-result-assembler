# Integração

**Estado: não integrado.** Nenhum dos três repositórios foi alterado. Este documento é o plano, não o registro de algo feito.

## Onde o assembler encaixa

O ponto exato existe e está vazio há tempo:

```python
# sentinela/workers/authoritative_engine.py:61
ConstruirResultado = Callable[[Any, Any], dict[str, Any]]
```

`construir_resultado` é um **parâmetro injetado sem implementação de produção** — todos os call-sites são testes com `{"summary": …}`. O assembler é a implementação que faltava:

```
engine_output → [produtor de facts] → analysis-facts-v1
                                    → assemble()
                                    → analysis-result-v1 → ResultadoDaAnalise.payload
```

`ResultadoDaAnalise` já carrega `result_schema_version` e `measurement_contract_version` (`workers/authoritative_cycle.py:74`). Os dois passam a valer `analysis-result-v1` e `measurement-1.0`.

## As seis lacunas, em ordem de dependência

| # | Lacuna | Onde | Por que bloqueia |
|---|---|---|---|
| **L1** | Nenhum produtor emite `analysis-facts-v1` | `sentinela/engine` | É o trabalho principal da integração |
| **L2** | `calculation_version` não existe no domínio | produtores | O contrato exige por indicador; sem ela não há como recusar número velho |
| **L3** | `measurement_contract_version` nunca recebe valor | pipeline inteiro | Precisa passar a valer `measurement-1.0` |
| **L4** | Nenhum produtor emite código ISO de moeda | `cost_estimators` | O contrato exige; os campos se chamam `*_usd`, o código precisa ser explícito |
| **L5** | `construir_resultado` sem implementação | `authoritative_engine.py` | É onde o assembler entra |
| **L6** | Composto `AI_HEALTH` não sai como fato | `_engine_helpers` | Dimensões ficam vazias até isso mudar |

L2, L3 e L4 são **mudanças no produtor**, não neste pacote. Fazê-las aqui significaria inventar do lado de cá o que o domínio deveria declarar — o oposto do propósito.

## Ordem sugerida

1. **Produtor de facts no `sentinela`** — um módulo que lê o `AnalysisResult` do domínio e emite `analysis-facts-v1`. Fecha L1, L2, L3, L4 de uma vez, porque emitir o contrato **obriga** a declarar versão e moeda.
2. **`construir_resultado` real** — chama `assemble()` e devolve `outcome.public_result`. Fecha L5.
3. **Manifesto na observabilidade** — `internal_manifest` para log/telemetria, tratado como dado interno (ver `SECURITY.md`).
4. **Dimensões** — quando `build_ai_health_measurement` sair como fato. Fecha L6.

## Contrato da fronteira

O consumidor precisa saber:

- **`parse_facts(payload)`** é a porta: erros de forma chegam como `SchemaMismatch`, da família `AssemblyError`. `AnalysisFacts.model_validate` levanta `pydantic.ValidationError`, que **não** é `AssemblyError`.
- **`assemble()` levanta ou devolve** — não existe resultado parcial. Toda `AssemblyError` tem `category` estável para mapear em resposta.
- **`serialize_canonical()`** produz os bytes a persistir. O `result_checksum` do manifesto é o hash desses bytes.
- **Retry é seguro**: a montagem é pura. Mesma entrada → mesmos bytes → mesmo checksum.

## Como o Orchestrator vai consumir

Como **biblioteca** (ADR-002), não serviço:

```python
from result_assembler import assemble, parse_facts, serialize_canonical

outcome = assemble(parse_facts(facts_payload))
result_json = serialize_canonical(outcome.public_result)   # → Result Store
manifesto = outcome.internal_manifest                       # → log interno
```

Sem rota, sem health check, sem deploy novo.

## O que a integração vai revelar (e este pacote não tem como saber)

- **Volume de indicadores por análise.** Hoje o registro tem 14; um produtor real pode emitir menos.
- **Se `calculation_version` é por indicador ou por análise.** O contrato assume por indicador (mais granular). Se o domínio só souber versionar o pipeline inteiro, a decisão vira uma versão só repetida — funciona, mas o registro deveria simplificar.
- **Se `USD` é sempre a moeda.** As fixtures declaram USD por derivação do nome do campo do produtor. Um tenant em BRL provaria se a suposição é do produtor ou do dado.

Estes três são perguntas honestas em aberto, não pendências deste pacote.
