"""Versões declaradas por este pacote.

Três eixos INDEPENDENTES — colapsá-los foi a armadilha que o discovery encontrou no
pipeline atual (`measurement_contract_version` viaja pelo sistema inteiro e nunca recebe
valor, então "versionado" era uma promessa vazia):

- `ASSEMBLER_VERSION`         quem montou (aparece só no manifesto interno);
- `FACTS_SCHEMA_VERSION`      forma da ENTRADA aceita;
- `RESULT_SCHEMA_VERSION`     forma da SAÍDA pública produzida.

A versão do *contrato de medição* NÃO é declarada aqui: ela pertence ao domínio
analítico e chega nos fatos. O assembler apenas verifica se ela está na lista de
versões que sabe traduzir.
"""

from __future__ import annotations

#: Versão desta implementação. Muda quando a MONTAGEM muda, mesmo sem mudar contrato.
ASSEMBLER_VERSION = "0.1.0"

#: Contrato de ENTRADA (interno, vindo do domínio analítico).
FACTS_SCHEMA_VERSION = "analysis-facts-v1"

#: Contrato de SAÍDA (público, consumido por Result Store → Gateway → frontend).
RESULT_SCHEMA_VERSION = "analysis-result-v1"

#: Contrato de saída do documento INTEGRADO (MF6.2): Engine facts + projeção pública.
#:
#: v2 e não um bloco aditivo no v1 porque `additionalProperties: false` torna QUALQUER acréscimo
#: uma quebra para quem valida contra o schema publicado — inclusive um campo opcional. A escolha
#: nunca foi "quebra × não quebra": era **quem** quebra. O v1 permanece exatamente como está.
RESULT_SCHEMA_V2_VERSION = "analysis-result-v2"

#: Contrato de ENTRADA que carrega as familias ANALITICAS e as formas que o v1 nao tinha.
#:
#: v2 pelo mesmo motivo do resultado: `additionalProperties: false` faz de qualquer acrescimo
#: uma quebra para quem valida contra o schema publicado, inclusive campo opcional. Um
#: documento v1 que trouxesse `alerts` seria invalido contra o proprio schema que ele declara.
FACTS_SCHEMA_V2_VERSION = "analysis-facts-v2"

#: Contrato de SAIDA publico do ARGOS completo. Nao carrega Analytics.
RESULT_SCHEMA_V3_VERSION = "analysis-result-v3"

#: Versões do contrato de MEDIÇÃO que este assembler sabe interpretar. Fail-closed:
#: uma versão fora desta lista é recusada, nunca montada "no melhor esforço".
SUPPORTED_MEASUREMENT_CONTRACT_VERSIONS: frozenset[str] = frozenset({"measurement-1.0"})

#: Versões do contrato de ENTRADA aceitas.
SUPPORTED_FACTS_SCHEMA_VERSIONS: frozenset[str] = frozenset(
    {FACTS_SCHEMA_VERSION, FACTS_SCHEMA_V2_VERSION}
)
