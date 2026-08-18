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
#:
#: **0.6.0** — a D5. `PublicMeasurement` e `FactMedida` ganharam `confidence`, e o
#: `behavior_score` (a #1 do catalogo, a ULTIMA das 37 saidas sem produtor) ganhou escala.
#:
#: O escore legado fundia qualidade e amostra num numero so: com comportamento PERFEITO ele
#: reportava apenas `n/10` — 30 com tres conversas, 100 com dez —, e noutra massa o
#: comportamento PIOR pontuou MAIS ALTO por ter amostra maior. `confidence` e agora dimensao
#: propria e NUNCA altera `value`.
#:
#: Junto: a tabela de escalas da spec passou a ser DERIVADA do registro
#: (`scripts/gerar_tabela_de_escalas.py --check`). Ela declarava `ratio_unit` para dois escores
#: que o produtor mede em 0..100, a D4 divergiu dela e ninguem viu — porque era prosa que
#: nenhum gate comparava. Agora o codigo e canonico e o documento e derivado.
#:
#: **0.5.0** — a D4. O `PublicIntent` e o `FactIntent` ganharam `semantic_drift`: a
#: dispersao das respostas DENTRO da intencao — "a IA da respostas muito diferentes para
#: perguntas parecidas". O motor ja a calculava por intencao (`mean_answer_similarity`) e a
#: descartava; eu a dei como sem produtor porque procurei pelo NOME. Junto vieram as escalas
#: de `consistency_score`, `global_confidence`, `cross_intent_similarity` e `semantic_drift`,
#: e o `intent_score` passou a vir do `governance_score` real (divida da D2).
#:
#: A montagem mudou — familia publica com campo novo e quatro escalas novas —, entao o numero
#: SOBE. Aditivo e barato hoje porque o v3 ainda nao tem cliente: os cadeados byte-a-byte sao
#: do v1, e o v3 valida contra o proprio schema, que se regenera.
#:
#: **0.4.0** — a D2. A ENTRADA ganhou o `analysis-facts-v3` com as quatro famílias
#: quantitativas (`scores`, `risks`, `projections`, `intents`) e o bloco de método; a porta
#: `parse_facts` passou a DESPACHAR pela versão declarada em vez de fixar o v1 — antes disso
#: um documento v2 ou v3 era recusado por `extra="forbid"`, e as famílias existiam no
#: contrato sem ter por onde entrar. O `assemble_v3` passou a chamar `validate_facts`, que
#: com três versões de entrada deixou de ser rigor e virou o único guarda contra montagem
#: em melhor esforço.
#:
#: Mesma regra de sempre: a MONTAGEM mudou, então o número sobe. O v1 e o v2 saem da
#: regeneração de schema byte a byte idênticos — medido, não suposto.
#:
#: **0.3.0** — a ordem canônica virou DUAS: `CANONICAL_ORDER_V1` congelada nos catorze do
#: v1 e `CANONICAL_ORDER_V3` derivando dela com quatro saídas novas do catálogo. Junto veio
#: uma versão de registro por versão de resultado: `indicator-registry-1.0` no v1/v2 e
#: `1.1` no v3.
#:
#: O número sobe pela mesma razão da 0.2.0, e ela vale como precedente: a MONTAGEM mudou.
#: Reconstruir a 0.2.0 com este conteúdo faria dois assemblers diferentes assinarem o
#: manifesto com o mesmo nome. A reconstrução da 0.1.0 foi o caso OPOSTO — mesmo intento de
#: código, artefato errado —, e por isso lá o número ficou e o `(source_commit, sha256)` do
#: lock carregou a identidade sozinho.
#:
#: **0.2.0** — o Recovery acrescentou `analysis-result-v3`, `analysis-facts-v2` e o catálogo
#: ARGOS. Este literal viaja no manifesto INTERNO de todo documento montado, então subi-lo
#: muda o manifesto — e é exatamente o que deve acontecer: o manifesto responde "quem
#: montou", e quem monta mudou. Mantê-lo em 0.1.0 faria dois assemblers diferentes
#: assinarem com o mesmo nome, que é o oposto de procedência.
#:
#: **0.7.0** — `PublicThresholds` e `FactThresholds`: os dois cortes que dividem a régua em
#: ok/atenção/crítico, em campo PRÓPRIO. A primeira versão da fatia os gravava em
#: `Scale.minimum/maximum` e a revisão adversarial derrubou — não por validação (a faixa é
#: verificada pela canônica do `kind`), mas porque o consumidor renderiza aqueles campos como
#: a RÉGUA: `behavior_score` apareceria dizendo `60–75` sendo um número que vive em 0..100.
#: Sem campo de orientação: a direção é função total da ordem (`critical < warn` = menor é
#: pior), e um campo afirmando o que a ordem já diz seria segunda cópia do mesmo fato.
ASSEMBLER_VERSION = "0.7.0"

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

#: Envelope de ENTRADA `analysis-facts-v3` — o v2 mais as familias QUANTITATIVAS
#: (`scores`, `risks`, `projections`, `intents`) e o bloco de METODO. Subclasse, e nao
#: campos opcionais no v2, pela mesma razao que o v2 nao virou campo opcional no v1.
FACTS_SCHEMA_V3_VERSION = "analysis-facts-v3"

#: Contrato de SAIDA publico do ARGOS completo. Nao carrega Analytics.
RESULT_SCHEMA_V3_VERSION = "analysis-result-v3"

#: Versões do contrato de MEDIÇÃO que este assembler sabe interpretar. Fail-closed:
#: uma versão fora desta lista é recusada, nunca montada "no melhor esforço".
SUPPORTED_MEASUREMENT_CONTRACT_VERSIONS: frozenset[str] = frozenset({"measurement-1.0"})

#: Versões do contrato de ENTRADA aceitas.
SUPPORTED_FACTS_SCHEMA_VERSIONS: frozenset[str] = frozenset(
    {FACTS_SCHEMA_VERSION, FACTS_SCHEMA_V2_VERSION, FACTS_SCHEMA_V3_VERSION}
)
