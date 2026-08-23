"""`analysis-facts-v1` — contrato de ENTRADA (interno).

Representa fatos que o domínio analítico **já calculou**. O assembler lê isto; nunca
produz um número que não esteja aqui.

Por que estes nomes: o discovery encontrou em `sentinela @ e7d0703` um contrato de
medição maduro (`core/contracts/measurement.py`) que já separa disponibilidade de valor,
com CINCO estados e motivo tipado. Este arquivo **espelha** aquele vocabulário em vez de
inventar outro — o perfil provisório da E5 tinha só três estados (`available`,
`not_measured`, `not_applicable`) e não sabia expressar "medido sobre subconjunto" nem
"tentou e falhou".

Tudo é `extra="forbid"`: campo não contratado é `schema_mismatch`, não é ignorado em
silêncio. Tudo é `frozen`: os fatos entram e não são mutados durante a montagem.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Any

from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator


class FactsModel(BaseModel):
    """Base estrita: proíbe campo extra e congela a instância."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _exigir_numero(v: Any) -> Any:
    """Rejeita tudo que não seja `int`/`float` ANTES da coerção do pydantic.

    Dois motivos, os dois encontrados por teste de propriedade e não por inspeção:

    - `True` viraria `1.0`, e aí `isinstance(1.0, bool)` já é False — bool passaria como
      medição válida;
    - `"0"` viraria `0.0`, e aí um produtor que serializa números como texto publicaria
      "zero medido" sem que ninguém tivesse medido zero.

    Coerção é conveniência de entrada de usuário. Aqui a entrada é outra máquina: tipo
    errado significa que o produtor está errado, e isso precisa aparecer.
    """
    if v is not None and (isinstance(v, bool) or not isinstance(v, int | float)):
        raise ValueError(f"esperado número (int/float), recebido {type(v).__name__}")
    return v


class Availability(str, Enum):
    """Estado da medição — NUNCA derivado do valor.

    Espelha `core/contracts/measurement.py::Availability` do domínio.
    """

    AVAILABLE = "available"  # medido; valor confiável (ZERO REAL entra aqui)
    PARTIAL = "partial"  # medido sobre subconjunto DECLARADO
    UNAVAILABLE = "unavailable"  # dado de entrada ausente ou insuficiente
    NOT_EVALUABLE = "not_evaluable"  # os dados existem, a métrica não se aplica
    FAILED = "failed"  # houve tentativa e erro explícito


class Reason(str, Enum):
    """Motivo tipado, para máquina. Espelha `MeasurementReason` do domínio."""

    OK = "ok"
    NO_INPUT_DATA = "no_input_data"
    INSUFFICIENT_SAMPLE = "insufficient_sample"
    SINGLE_GROUP = "single_group"
    MISSING_DIMENSION = "missing_dimension"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    NOT_APPLICABLE = "not_applicable"
    COMPUTATION_ERROR = "computation_error"


class IndicatorKind(str, Enum):
    """Natureza do valor. Decide a formatação PERMITIDA — e nada além dela.

    `ratio` é a única autorização para virar percentual na apresentação. A conversão em
    si NÃO acontece aqui nem no assembler: pertence ao frontend.
    """

    RATIO = "ratio"  # fração 0..1 declarada pela origem
    COUNT = "count"  # contagem absoluta — nunca percentual
    CURRENCY = "currency"  # valor monetário
    SCALAR = "scalar"  # número sem unidade semântica (ex.: variância)


class Denominator(FactsModel):
    """Sobre o QUE a razão foi calculada. Sem isto, `ratio` é um número solto.

    O discovery achou o custo de não ter isto: `outcome_coverage` (cobertura de campo
    `outcome`) e `intent_coverage_rate` (intenções cobertas) são ambos "coverage 0.85" na
    superfície, e significam coisas diferentes.
    """

    kind: str = Field(min_length=1)  # ex.: "records", "intents", "sessions"
    #: `gt=0` no FIELD, não em validador: assim a restrição atravessa para o JSON Schema
    #: publicado (Codex R2 [2]). Um schema mais permissivo que o modelo é pior que schema
    #: nenhum — o produtor valida contra ele, passa, e só descobre na biblioteca.
    value: float = Field(gt=0)

    @field_validator("value", mode="before")
    @classmethod
    def _so_numero(cls, v: Any) -> Any:
        return _exigir_numero(v)

    @field_validator("value")
    @classmethod
    def _finito(cls, v: float) -> float:
        # JSON não tem NaN/Infinity, mas a entrada em Python pode ter.
        if not math.isfinite(float(v)):
            raise ValueError("denominador precisa ser finito")
        return float(v)


class FactIndicator(FactsModel):
    """Um indicador já calculado pelo domínio."""

    id: str = Field(min_length=1)
    kind: IndicatorKind
    availability: Availability
    reason: Reason = Reason.OK

    #: `None` sempre que não houver medição. NUNCA 0 para representar ausência.
    value: float | None = None
    unit: str | None = None
    currency: str | None = None
    denominator: Denominator | None = None

    #: Fração da entrada efetivamente medida (obrigatória em `partial`). A faixa fica no
    #: FIELD para o JSON Schema publicado carregá-la (Codex R2 [3]).
    data_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    observed_units: int | None = Field(default=None, ge=0)
    expected_units: int | None = Field(default=None, gt=0)

    #: Versão do CÁLCULO que produziu este valor — não a do contrato nem a do assembler.
    calculation_version: str = Field(min_length=1)
    #: Origem observável: qual função/módulo do domínio produziu.
    source: str = Field(min_length=1)

    @field_validator("value", "data_coverage", mode="before")
    @classmethod
    def _so_numero(cls, v: Any) -> Any:
        return _exigir_numero(v)

    @field_validator("value")
    @classmethod
    def _valor_finito(cls, v: float | None) -> float | None:
        if v is None:
            return None
        if not math.isfinite(float(v)):
            raise ValueError("value precisa ser finito")
        return float(v)

    @field_validator("data_coverage")
    @classmethod
    def _cobertura_finita(cls, v: float | None) -> float | None:
        # A faixa está no Field (e portanto no schema); aqui sobra só o que JSON não
        # consegue expressar.
        if v is not None and not math.isfinite(float(v)):
            raise ValueError("data_coverage precisa ser finito")
        return None if v is None else float(v)


class FactDimension(FactsModel):
    """Uma dimensão analítica (ex.: `semantic`, `economic`) já composta pelo domínio."""

    id: str = Field(min_length=1)
    availability: Availability
    reason: Reason = Reason.OK
    #: Dimensão é composto normalizado 0..1 no domínio (`aggregate_health`).
    value: float | None = Field(default=None, ge=0.0, le=1.0)
    data_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    calculation_version: str = Field(min_length=1)
    source: str = Field(min_length=1)

    @field_validator("value", "data_coverage", mode="before")
    @classmethod
    def _so_numero(cls, v: Any) -> Any:
        return _exigir_numero(v)

    @field_validator("value")
    @classmethod
    def _valor_finito(cls, v: float | None) -> float | None:
        if v is not None and not math.isfinite(float(v)):
            raise ValueError("value precisa ser finito")
        return None if v is None else float(v)


class FactRecommendation(FactsModel):
    """Recomendação JÁ priorizada e ordenada pelo domínio.

    O discovery confirmou que `engine/recommendations/recommendation_ranker.py` já produz
    `priority` (P1..P4) e `priority_score`, e que `output_consolidator` já ordena. O
    assembler transporta — não escolhe a principal, não reordena por impacto inventado.
    """

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    #: Prioridade declarada pelo domínio. Obrigatória: sem ela não há como transportar
    #: ordem sem inventar.
    priority: str = Field(min_length=1)
    #: Posição explícita na ordem do domínio (0-based, sem repetição).
    order: int = Field(ge=0)
    category: str | None = None
    #: Ids de evidência relacionados (precisam existir na seção de evidências).
    evidence_refs: tuple[str, ...] = ()


#: Teto do trecho de evidência. Um excerto é um excerto.
#:
#: Publicar a conversa inteira seria republicar o dataset pelo documento de resultado — que é
#: outra coisa, e tem outra porta (o export, com retenção e auditoria próprias).
MAX_EXCERPT_LEN: Final = 400


class FactEvidenceSummary(FactsModel):
    """Resumo de evidência — agregado, **e agora com o trecho observado**.

    ## A regra anterior caiu, e a premissa dela é que mudou

    Este docstring dizia *"não carrega texto livre de conversa, prompt, resposta"*. Decisão do
    owner: evidência sem o texto observado não é evidência — o texto é justamente o que mostra
    ONDE o problema está, e é o que dá nome à família.

    A regra não cai por conveniência. Quando ela foi escrita, **oito das onze peças de
    privacidade não tinham chamador de produção** — está no cabeçalho do `gate.py` da Ingestão.
    Ela era a defesa certa para aquele mundo. O `ING-PRIVACY-WIRING-05` fiou as peças.

    Hoje:

    * o Privacy Gate é **porta única** — o pipeline canônico não grava sem passar por ela;
    * ele detecta e transforma sete classes fechadas: identificador direto (CPF, telefone,
      e-mail, nome completo, RG), quase-identificador, atributo sensível, credencial, segredo,
      identificador financeiro e identificador de rede;
    * o clearance é **estruturalmente garantido**: `orchestrator_ingestion_inbox` tem
      `check (privacy_clearance = 'passed')`. A existência da linha É a prova;
    * cada dataset carrega `privacy_policy_version` e um manifesto com `values_redacted_count`.

    ## O que continua valendo

    Caminho, chave, credencial e id interno seguem PROIBIDOS, e a varredura de segurança confere
    campo a campo — inclusive no trecho. O Gate cobre o dado do cliente; a varredura cobre o que
    o nosso lado poderia colar ali.
    """

    id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    #: Quantos itens sustentam a evidência. Agregado — e continua sendo o número que importa.
    observed_count: int = Field(ge=0)
    #: Rótulo curto e já sanitizado pelo domínio (ex.: nome de intenção).
    label: str | None = None
    #: O TRECHO observado, já sanitizado pelo Privacy Gate e cortado no teto.
    #:
    #: `None` quando o produtor não tem trecho para aquela evidência — e isso é comum: nem toda
    #: evidência é textual. Ausência aqui não é "não achamos"; é "esta evidência não é texto".
    excerpt: str | None = Field(default=None, max_length=MAX_EXCERPT_LEN)


class FactsIdentity(FactsModel):
    """Identidade da análise. `analysis_id` é o único id que atravessa para o público."""

    analysis_id: str = Field(min_length=1)
    #: Ids internos — ficam no manifesto, nunca no resultado público.
    job_id: str | None = None
    analysis_run_id: str | None = None


class AnalysisWindow(FactsModel):
    """Quando e sobre quanto a análise foi feita. Datas vêm como FATO.

    `analyzed_at` é obrigatório: o assembler não tem relógio. Fabricar a data aqui seria
    a mentira mais barata de detectar e a mais cara de descobrir em produção.
    """

    analyzed_at: str = Field(min_length=1)  # ISO-8601, produzido pelo domínio
    record_count: int = Field(ge=0)


class CalculationProvenance(FactsModel):
    """De onde os números vieram. Vai para o manifesto interno; não para o público."""

    engine_version: str = Field(min_length=1)
    analysis_version: str | None = None
    dataset_fingerprint: str | None = None



class FactAlert(FactsModel):
    """Um alerta detectado pelo dominio. **Saida analitica, nao metrica.**

    A CONTAGEM de alertas criticos e metrica (`critical_alert_count`, no catalogo). Isto e
    o conteudo. Publicar os dois na mesma familia apagaria a diferenca entre "quantos" e
    "quais", e so a primeira e comparavel entre analises.
    """

    id: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    #: Estavel, para maquina. O titulo e para gente e pode mudar de redacao sem que o
    #: alerta mude de natureza — por isso os dois campos, e nao um.
    code: str = Field(min_length=1)
    title: str = Field(min_length=1)
    detail: str | None = None
    evidence_refs: tuple[str, ...] = ()
    affected_intents: tuple[str, ...] = ()


class FactIssue(FactsModel):
    """Um problema estrutural detectado. Distinto de alerta: alerta pede atencao agora."""

    id: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    code: str = Field(min_length=1)
    title: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()


class FactExecutiveSummary(FactsModel):
    """O resumo executivo, textual.

    `language` e obrigatorio. Um texto sem idioma declarado nao tem como ser apresentado
    honestamente a quem le noutro — e o `PublicSummary` do v1, que so tem `analyzed_at` e
    `record_count`, nunca teve onde guardar nem o texto nem o idioma.
    """

    language: str = Field(min_length=2)
    text: str = Field(min_length=1)
    generated_by: str = "engine"


class AnalysisFacts(FactsModel):
    """Envelope de entrada `analysis-facts-v1`."""

    facts_schema_version: str = Field(min_length=1)
    measurement_contract_version: str = Field(min_length=1)
    identity: FactsIdentity
    window: AnalysisWindow
    provenance: CalculationProvenance
    indicators: tuple[FactIndicator, ...] = ()
    dimensions: tuple[FactDimension, ...] = ()
    recommendations: tuple[FactRecommendation, ...] = ()
    evidence: tuple[FactEvidenceSummary, ...] = ()


class AnalysisFactsV2(AnalysisFacts):
    """Envelope `analysis-facts-v2` — o v1 mais as familias ANALITICAS.

    Subclasse, e nao campos opcionais no v1, pela mesma razao que o `analysis-result-v2` e
    um arquivo a parte: `additionalProperties: false` faz de qualquer acrescimo uma quebra
    para quem valida contra o schema publicado. Um documento v1 que trouxesse `alerts` seria
    invalido contra o proprio schema que ele declara — e ninguem notaria ate um validador
    externo reclamar.

    Assim o schema do v1 fica intocado, byte a byte, e o v2 tem o seu.

    `None` e ausencia de PRODUTOR; `()` e produtor que rodou e nao achou.
    """

    alerts: tuple[FactAlert, ...] | None = None
    issues: tuple[FactIssue, ...] | None = None
    executive_summary: FactExecutiveSummary | None = None

    @model_validator(mode="after")
    def _declara_a_versao_certa(self) -> "AnalysisFactsV2":
        from result_assembler.version import FACTS_SCHEMA_V2_VERSION

        if self.facts_schema_version != FACTS_SCHEMA_V2_VERSION:
            raise ValueError(
                f"`AnalysisFactsV2` exige `{FACTS_SCHEMA_V2_VERSION}`; recebido "
                f"`{self.facts_schema_version}`"
            )
        return self


class FactThresholds(FactsModel):
    """Os dois cortes que o produtor aplica a um número: ok, atenção, crítico.

    Bloco próprio, e **não** dois campos soltos na medida: `warn` e `critical` só têm sentido
    JUNTOS. Soltos, um fato com `warn` e sem `critical` seria representável — e metade de um
    par de cortes não divide zona nenhuma, além de deixar a direção indeterminada.

    NÃO é a escala. A escala é a régua (`score_100` = 0..100); isto são os cortes NELA. A
    primeira versão desta fatia gravava os cortes em `Scale.minimum/maximum` e a revisão
    adversarial a derrubou: o consumidor renderiza aqueles dois campos como a régua, então
    `behavior_score` apareceria dizendo `60–75` sendo um número que vive em 0..100.

    **A ordem carrega a direção**, e por isso não há campo de orientação: `critical < warn` é
    menor-é-pior, `critical > warn` é maior-é-pior. Um campo afirmando o que a ordem já diz
    seria segunda cópia do mesmo fato, com um validador para reconciliá-las — exatamente o
    arranjo que a Regra 14 existe para impedir.
    """

    warn: float
    critical: float

    @field_validator("warn", "critical", mode="before")
    @classmethod
    def _so_numero(cls, v: Any) -> Any:
        return _exigir_numero(v)

    @field_validator("warn", "critical")
    @classmethod
    def _corte_finito(cls, v: float) -> float:
        if not math.isfinite(float(v)):
            raise ValueError("limiar precisa ser finito")
        return float(v)

    @model_validator(mode="after")
    def _cortes_distintos(self) -> FactThresholds:
        if self.warn == self.critical:
            raise ValueError(
                f"limiares iguais (`{self.warn}`): sem zona do meio, e sem a ordem não há "
                "como saber de que lado da régua fica o ruim"
            )
        return self


class FactMedida(FactsModel):
    """A parte MEDIDA de um fato, sem a identidade da família.

    Existe porque escore, risco e projeção são a mesma coisa por baixo — um valor com
    disponibilidade, motivo, cobertura e procedência — e só diferem no que a família
    acrescenta. Ter três cópias dos invariantes seria três lugares para eles divergirem.

    `FactIndicator` **não** herda daqui, e isso é deliberado: o `analysis-facts-v1` tem o
    schema publicado congelado byte a byte, e refatorá-lo para uma base comum reordenaria
    as propriedades do documento sem que nenhum campo tivesse mudado. A duplicação com o
    indicador é o preço de não mexer num contrato congelado.
    """

    id: str = Field(min_length=1)
    availability: Availability
    reason: Reason = Reason.OK

    #: `None` sempre que não houver medição. NUNCA 0 para representar ausência.
    value: float | None = None
    data_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    #: Confianca DESTA medicao. Distinta de `global_confidence`, que e uma saida da analise.
    #: Nunca altera `value` — sao dimensoes diferentes do mesmo fato.
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    #: Versão do CÁLCULO que produziu este valor — não a do contrato nem a do assembler.
    calculation_version: str = Field(min_length=1)
    #: Origem observável: qual função/módulo do domínio produziu.
    source: str = Field(min_length=1)

    #: Os dois cortes que o produtor aplica a ESTE número, quando aplica.
    #:
    #: Vem do produtor ou não vem: nenhuma camada entre o motor e a tela tem autoridade para
    #: derivar onde começa o "bom". `None` é o caso majoritário — o motor aplica um par de
    #: limiares a duas das 39 saídas — e é honesto, não lacuna.
    #:
    #: O limiar é validado aqui **e** no público, e os dois não são o mesmo cadeado: este é a
    #: fronteira de ENTRADA (produtor externo manda fato inválido → recusa na porta, com o
    #: nome do produtor no rastro), e o público é a de SAÍDA (montagem produz documento
    #: inválido → recusa antes do consumidor). Um par invertido que passasse só a primeira
    #: seria fato aceito e documento impossível, e o erro apareceria a dois hops da causa.
    thresholds: FactThresholds | None = None

    @field_validator("value", "data_coverage", mode="before")
    @classmethod
    def _so_numero(cls, v: Any) -> Any:
        return _exigir_numero(v)

    @field_validator("value")
    @classmethod
    def _valor_finito(cls, v: float | None) -> float | None:
        if v is None:
            return None
        if not math.isfinite(float(v)):
            raise ValueError("value precisa ser finito")
        return float(v)

    @field_validator("data_coverage")
    @classmethod
    def _cobertura_finita(cls, v: float | None) -> float | None:
        if v is not None and not math.isfinite(float(v)):
            raise ValueError("data_coverage precisa ser finito")
        return None if v is None else float(v)


class FactScore(FactMedida):
    """Um escore global. NÃO é dimensão de saúde, e não é indicador.

    `composite_of` só é preenchido em composto. O `ai_health_score` declara as quatro
    dimensões que o formam — e é isso que impede uma agregação sobre `dimensions[]` somar
    o agregado junto das partes.
    """

    composite_of: tuple[str, ...] = ()
    #: Janela metodológica. Obrigatória em drift: ele é medido DENTRO de uma análise, e sem
    #: a janela declarada dois valores de análises diferentes pareceriam série.
    window_kind: str | None = None
    window_size: float | None = None


class FactRisk(FactMedida):
    """Um risco calculado pelo domínio.

    `band` vem do PRODUTOR ou não vem. Nenhuma camada intermediária a calcula: escolher
    onde termina "moderado" é decisão de produto, e tomá-la na apresentação a esconderia
    de quem a revisa.
    """

    band: str | None = None


class FactProjection(FactMedida):
    """Uma projeção monetária, com horizonte e base declarados.

    `horizon` é DADO e não faz parte do nome: `projected_token_cost` em `month` e em `year`
    é a mesma métrica em dois horizontes. Codificar o horizonte no id faria quatro métricas
    onde há duas.

    `basis` existe porque projeção sem base declarada é adivinhação com casas decimais —
    é a distinção observado/estimado/projetado dentro do próprio fato.
    """

    horizon: str = Field(min_length=1)
    currency: str | None = None
    basis: str | None = None


class FactIntent(FactsModel):
    """O grão fino por intenção.

    Achatar isto em `indicators[]` perderia a identidade da intenção: seis intenções
    virariam seis indicadores com ids sintéticos.

    `underrepresented` NÃO entra aqui: o consumidor o deriva de `support` contra
    `min_samples_per_intent`, que são os dois publicados. Mandá-lo pronto criaria uma
    segunda verdade sobre o mesmo fato.
    """

    intent_id: str = Field(min_length=1)
    score: FactMedida
    #: Conversas observadas nesta intenção. É o denominador da confiança.
    support: int = Field(ge=0)
    severity: str | None = None
    #: POR QUE o veredito é esse. Códigos do produtor, na ordem em que ele os emitiu.
    #:
    #: Existe porque `severity` **não é função do escore**: o motor escala para `WARN` por
    #: evidência de mismatch semântico independentemente da nota
    #: (`core/_sentinela_governance.py:161`). Medido com o motor real: uma intenção com
    #: `governance_score = 100` sai `severity = WARN`. Publicado o limiar, aquela nota cai na
    #: zona verde — e sem o motivo a tela mostra bullet verde ao lado de crachá WARN, com nada
    #: explicando. Veredito sem explicação é o defeito que esta frente inteira vem desfazendo.
    #:
    #: `None` ≠ `()`. `None` é produtor que **não declara** o motivo (motor anterior a esta
    #: fatia); `()` é produtor que declarou e não há motivo — o caso legítimo de `severity=OK`
    #: limpo. A distinção é o que permite o invariante abaixo sem recusar dado antigo.
    #:
    #: Vocabulário ABERTO, como o do próprio `severity`. Fechá-lo num enum faria um código novo
    #: no motor derrubar a montagem; aberto, ele chega ao consumidor, que é quem precisa decidir
    #: o que fazer com um código que ainda não sabe traduzir.
    severity_reason: tuple[str, ...] | None = None

    @model_validator(mode="after")
    def _veredito_ruim_explica_por_que(self) -> FactIntent:
        """Produtor que fala precisa explicar um veredito não-OK.

        Verificado exaustivamente contra o motor antes de contratar: varredura de 384
        combinações de `(score, penalidade, mismatch_ratio, mismatch_confidence)` — **zero**
        casos de `severity != OK` sem motivo, e `severity == OK` com
        `("CROSS_INTENT_PENALTY",)` é caso REAL, que por isso não é proibido aqui.

        Só morde quando `severity_reason` não é `None`: um fato de produtor antigo, que nunca
        declarou o campo, continua válido. Recusá-lo transformaria uma melhoria em quebra.
        """
        if self.severity_reason is None:
            return self
        veredito = (self.severity or "OK").strip().upper()
        if veredito not in {"", "OK"} and not self.severity_reason:
            raise ValueError(
                f"`{self.intent_id}`: `severity={self.severity}` com `severity_reason` vazio — "
                "veredito não-OK sem motivo é exatamente o que a tela não consegue explicar"
            )
        return self
    response_variance: FactMedida | None = None
    response_stability: FactMedida | None = None
    #: D4 — `1 - mean_answer_similarity` DENTRO da intencao: quao diferentes sao as respostas
    #: dadas a perguntas parecidas. MAIOR E PIOR. `Medida` e nao `float` porque intencao com
    #: uma unica conversa nao tem PAR, logo nao tem similaridade — e um float puro teria de
    #: escolher entre mentir (`0.0`) e omitir (sem motivo).
    semantic_drift: FactMedida | None = None


class FactMethod(FactsModel):
    """Os PARÂMETROS do método. Não são medidas, e é por isso que têm bloco próprio.

    `min_samples_per_intent` publicado como indicador pareceria algo que a amostra revelou,
    quando é configuração de quem mediu.


    A MOEDA não mora aqui, embora o `MethodMetadata` público a tenha. Ela já é lida dos
    fatos monetários (`_moeda_declarada`), que é onde ela viajou junto do valor desde o
    dataset. Aceitá-la também por este bloco daria duas fontes para o mesmo fato, e no dia
    em que discordassem não haveria como saber qual estava certa.
    """

    #: `ge=1`: zero amostras por intenção não é um limiar, é a ausência de um.
    min_samples_per_intent: int | None = Field(default=None, ge=1)


class AnalysisFactsV3(AnalysisFactsV2):
    """Envelope `analysis-facts-v3` — o v2 mais as famílias QUANTITATIVAS.

    Subclasse pela mesma razão do v2: `additionalProperties: false` faz de qualquer
    acréscimo uma quebra para quem valida contra o schema publicado, inclusive campo
    opcional. Herda do v2 e não do v1 porque o v3 é o v2 mais estas famílias — quem já
    emite as analíticas sobe sem perdê-las.

    As quatro famílias entram num ÚNICO bump mesmo que nem todas tenham produtor no dia da
    estreia. Declará-las uma a uma custaria quatro versões quebrando; e o vocabulário para
    "declarada e ainda não produzida" já existe:

    `None` e ausencia de PRODUTOR; `()` e produtor que rodou e nao achou.
    """

    scores: tuple[FactScore, ...] | None = None
    risks: tuple[FactRisk, ...] | None = None
    projections: tuple[FactProjection, ...] | None = None
    intents: tuple[FactIntent, ...] | None = None
    method: FactMethod | None = None

    @model_validator(mode="after")
    def _declara_a_versao_certa(self) -> "AnalysisFactsV3":
        from result_assembler.version import FACTS_SCHEMA_V3_VERSION

        if self.facts_schema_version != FACTS_SCHEMA_V3_VERSION:
            raise ValueError(
                f"`AnalysisFactsV3` exige `{FACTS_SCHEMA_V3_VERSION}`; recebido "
                f"`{self.facts_schema_version}`"
            )
        return self
