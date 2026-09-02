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
#:
#: **0.8.0** — `PublicIntent.severity_reason` e `FactIntent.severity_reason`. `severity`
#: NAO e o limiar aplicado ao escore: o motor a escala para `WARN` por evidencia de
#: mismatch semantico sem olhar a nota, e medido com o motor real uma intencao com escore
#: `100` sai `WARN`. Com o limiar da 0.7.0 publicado, `100` cai na zona verde — a tela
#: pintaria verde ao lado de um cracha de atencao, sem nada explicando. TRES estados
#: (`None` / `()` / preenchido), porque `severity=WARN` com `[]` so pode vir de produtor
#: antigo, e a tela precisa poder dizer "motivo nao publicado".
#: **0.9.0** — `PublicEvidenceSummaryV3.excerpt` e `FactEvidenceSummary.excerpt`: a evidencia
#: passa a carregar o TRECHO observado.
#:
#: Decisao do owner. A regra que a proibia — *"nao carrega texto livre de conversa"* — cai
#: sobre uma premissa que mudou: quando ela foi escrita, oito das onze pecas de privacidade da
#: Ingestao nao tinham chamador de producao. Hoje o Privacy Gate e porta unica, cobre sete
#: classes fechadas de dado sensivel, e o clearance e garantido por
#: `check (privacy_clearance = 'passed')` no banco.
#:
#: ⚠️ **ORDEM DE DEPLOY.** `FactsModel` e `extra="forbid"`: um produtor que envia `excerpt`
#: contra a 0.8.0 faz a validacao do envelope FALHAR, e a analise sai sem resultado. Esta
#: versao entra ANTES do produtor que a usa, nunca depois.
#:
#: O modelo do v3 e proprio (`PublicEvidenceSummaryV3`). O compartilhado serve v1 e v2, que tem
#: `additionalProperties: false` no schema publicado — campo novo ali e quebra para quem valida.
#:
#: Junto: `assemble_v3` passou a chamar `validate_evidence_safety`, que ele NUNCA chamava. O v1
#: e o v2 chamavam; o caminho de producao era o unico sem varredura de conteudo. E a varredura
#: passou a cobrir `alerts`, por onde um trecho de conversa vazava sem contrato nem teto.
ASSEMBLER_VERSION = "1.0.2"

# ⚠️ 0.9.3 — `intent_id` e `affected_intents` sao texto DO CLIENTE, e a regua deles mudou.
#
# A 0.9.2 fechou um achado de alcance da varredura: `intent_id`, `severity_reason` e
# `affected_intents` eram publicados sem rede. Eles entraram JUNTOS, com a regua do rotulo de
# maquina — e nao tem a mesma origem.
#
# Medido em homologacao com massa real de cliente: uma intencao chamada **`senha`** —
# recuperacao de senha, das mais comuns que existem em suporte — batia no padrao `credencial`:
#
#     MONTAGEM RECUSADA: conteudo proibido (credencial) [em intents[10].intent_id]
#
# E o MESMO defeito que a 0.9.1 consertou no trecho, repetido num campo que o proprio conserto
# adicionou. `intent_id` e a taxonomia do cliente: ele escolhe os nomes.
#
# Agora `_varrer_do_cliente` aplica so os padroes `NO_TRECHO` (vazamento NOSSO) aos campos de
# origem do cliente. `severity_reason` e prosa do MOTOR e mantem a regua cheia.
#
# RECUSA, e nao descarta como o trecho: `intent_id` e CHAVE — liga a intencao aos alertas e ao
# rotulo da evidencia. Descartar quebraria a integridade referencial do documento.

# ⚠️ 0.9.2 — o que a REVISAO INDEPENDENTE achou no proprio conserto da 0.9.1.
#
# A 0.9.1 tirou o padrao `url` do trecho porque um link de ajuda da empresa e prosa de suporte
# comum. O corte foi LARGO DEMAIS: junto com o link banal saiu a deteccao de STRING DE CONEXAO,
# que era o unico padrao que a pegava. Medido:
#
#     "DATABASE_URL=postgres://analytics:supersecret@db.internal/prod"  -> publicava
#     "postgres://user:senha123@db.internal:5432/sentinela"             -> publicava
#     "redis://:token@redis-homol.railway.internal:6379"                -> publicava
#
# Isso e vazamento NOSSO plausivel, nao prosa de cliente. Tres padroes novos, todos `NO_TRECHO`:
# `credencial em url` (`scheme://user:pass@`), `dsn de infraestrutura` (postgres/redis/amqp/...)
# e `variavel de ambiente` (`*_URL=`, `*_TOKEN=`, `*_SECRET=`).
#
# A contraparte tem caso: `https://ajuda.acme.com/conta` e `www.exemplo.com/ajuda` continuam
# atravessando. Sem os dois lados, "consertar" vira barrar tudo de novo.
#
# Junto: `trecho_publicavel` passou a cumprir a promessa "NUNCA levanta" de forma absoluta — uma
# SUBCLASSE hostil de `str` passava pela guarda de tipo e explodia dentro do `re`.

# ⚠️ 0.9.1 — O QUE MUDOU, e por que e uma versao e nao um patch silencioso.
#
# A 0.9.0 ligou `validate_evidence_safety` no caminho de producao (`assemble_v3`) e, no MESMO
# passo, comecou a alimentar a familia `evidence` com texto de conversa. As duas coisas juntas
# criaram um defeito que a revisao da Regra #16 pegou: a rede foi escrita para ROTULO de maquina
# e passou a julgar PROSA DE CLIENTE.
#
# Medido — tres respostas de suporte normais derrubavam a analise INTEIRA (409 nao-retryable,
# nenhum documento, nem v3 nem v1):
#
#     "Voce pode alterar a senha no aplicativo"       -> padrao `credencial`
#     "Para redefinir sua senha, acesse https://..."  -> padrao `url`
#     "Please select your plan from the list below"   -> padrao `sql/tabela`
#
# 0.9.1 separa as duas responsabilidades:
#
#   * campos NOSSOS (`id`, `kind`, `label`, `evidence_refs`, texto de alerta, `intent_id`,
#     `severity_reason`, `affected_intents`) continuam RECUSANDO — defeito nosso nao publica;
#   * o `excerpt`, cujo conteudo e do CLIENTE por decisao, e DESCARTADO por `trecho_publicavel`
#     e o documento sai. Mesma garantia de privacidade, sem custar o resultado.
#
# Junto: `affected_intents`, `intent_id` e `severity_reason` entraram na varredura (eram
# publicados sem rede); `PublicEvidenceSummaryV3.excerpt` ganhou `max_length` para o teto
# atravessar ao schema PUBLICADO; e o nome da tabela interna saiu das docstrings que viram
# `description` no schema.
#
# COMPATIBILIDADE: nao ha mudanca de forma. Um produtor 0.9.0 funciona contra 0.9.1 e vice-versa.
# A ordem de deploy rigida da 0.9.0 (montador ANTES do produtor) continua valendo para quem ainda
# estiver em 0.8.0.

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
FACTS_SCHEMA_V4_VERSION = "analysis-facts-v4"

#: Contrato de SAIDA publico do ARGOS completo. Nao carrega Analytics.
RESULT_SCHEMA_V3_VERSION = "analysis-result-v3"
RESULT_SCHEMA_V4_VERSION = "analysis-result-v4"

#: Versões do contrato de MEDIÇÃO que este assembler sabe interpretar. Fail-closed:
#: uma versão fora desta lista é recusada, nunca montada "no melhor esforço".
SUPPORTED_MEASUREMENT_CONTRACT_VERSIONS: frozenset[str] = frozenset({"measurement-1.0"})

#: Versões do contrato de ENTRADA aceitas.
SUPPORTED_FACTS_SCHEMA_VERSIONS: frozenset[str] = frozenset(
    {
        FACTS_SCHEMA_VERSION,
        FACTS_SCHEMA_V2_VERSION,
        FACTS_SCHEMA_V3_VERSION,
        FACTS_SCHEMA_V4_VERSION,
    }
)
