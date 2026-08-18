"""`analysis-result-v3` — o contrato público do ARGOS, e só do ARGOS.

## Por que uma v3

O discovery de 2026-08-12 mediu **8** das 34 métricas documentadas chegando ao contrato
público. As outras não foram recusadas: elas não cabiam. O v1 publica `indicators[]` — uma
lista de escalares com unidade e denominador — e um escore global, uma dimensão de saúde,
uma métrica por intenção, um risco e uma projeção **não são a mesma forma**. Achatá-las ali
teria perdido o que o produtor sabia.

Três contratos, três destinos:

    analysis-result-v1   Engine facts, 14 indicadores. Mantido, imutável.
                         `additionalProperties: false` em 8 pontos — não cresce.
    analysis-result-v2   Engine facts + projeção Analytics. Congelado como legado.
                         Não é ampliado semanticamente.
    analysis-result-v3   ARGOS completo, só ARGOS.        <- este arquivo

O v3 **não** carrega Analytics. Os dois motores publicam em contratos próprios, e a
colisão de nome `dimensions` — que no Analytics são distribuições categóricas e aqui são as
quatro dimensões de saúde — deixa de ser um risco por morarem em documentos diferentes.

## O envelope, e o que ele resolve

`PublicMeasurement` separa **valor** de **disponibilidade**. É o que destrava
`consistency_score` e `global_confidence`, excluídos do v1 por absence-as-zero: o produtor
devolvia `0.0` sem dado, e um zero medido é uma afirmação sobre o negócio. Com o envelope,
ausência tem nome e motivo.

## Omitido × vazio

    campo omitido   a capacidade/produtor NÃO EXISTE neste documento
    []              a capacidade existe, executou, e produziu zero itens

Nunca `[]` para "não implementado". Foi assim que `evidence: []` — fixo no producer, sem
produtor algum atrás — passou anos parecendo resposta.
"""

from __future__ import annotations

import math
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from result_assembler.contracts.facts import Availability, Reason
from result_assembler.contracts.result import (
    IndicatorState,
    Partiality,
    PublicDenominator,
    PublicEvidenceSummary,
    PublicRecommendation,
    PublicSummary,
)

RESULT_V3_SCHEMA_VERSION = "analysis-result-v3"


class ResultV3Model(BaseModel):
    """Base estrita. `extra="forbid"` é o que fez o defeito aparecer em vez de passar calado."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# ═══════════════════════════════════════════════════════════════════════════════════════
# Escala — contrato, não escolha de implementação
# ═══════════════════════════════════════════════════════════════════════════════════════


class ScaleKind(str, Enum):
    """A faixa em que o número vive. Declarada, nunca inferida.

    `SCORE_100` existe porque `response_stability` é produzido em 0..100 e **é publicado
    assim**. Dividir por 100 na fronteira de publicação seria normalização numérica não
    autorizada: mudar a escala de uma medida é decisão metodológica do produtor, e um
    consumidor que recebe 0..1 onde o motor mediu 0..100 não tem como saber que a conversão
    aconteceu.
    """

    RATIO_UNIT = "ratio_unit"  # 0..1
    SCORE_100 = "score_100"  # 0..100
    PERCENT = "percent"  # 0..100, lido como porcentagem
    CURRENCY = "currency"  # ISO-4217, faixa aberta
    COUNT = "count"  # inteiro ≥ 0
    DURATION = "duration"  # tempo, unidade no campo `unit`
    RAW = "raw"  # sem faixa contratada


class Scale(ResultV3Model):
    """A escala declarada de uma medição."""

    kind: ScaleKind
    minimum: float | None = None
    maximum: float | None = None


#: As escalas cuja faixa é fechada e conhecida. Usadas para validar o valor.
_FAIXAS_CANONICAS: dict[ScaleKind, tuple[float, float]] = {
    ScaleKind.RATIO_UNIT: (0.0, 1.0),
    ScaleKind.SCORE_100: (0.0, 100.0),
    ScaleKind.PERCENT: (0.0, 100.0),
}


class PublicThresholds(ResultV3Model):
    """Os dois cortes que dividem a régua em três zonas: ok, atenção, crítico.

    **Não é a escala, e não mora nela.** `Scale` é a régua — *"a faixa em que o número vive"* —
    e o consumidor a escreve como régua: `medicaoV3.escalaEscrita` renderiza
    `minimum–maximum` em três lugares da tela. Um limiar gravado ali apareceria rotulado como
    a régua de um número que vive noutra: `behavior_score` diria `60–75` sendo `score_100`.
    Duas verdades para um fato, na tela, e sem um teste vermelho — a revisão adversarial
    derrubou exatamente essa primeira versão do desenho.

    **Não é a severidade.** `PublicIntent.severity` já traz o veredito do produtor
    (`OK`/`WARN`/`CRITICAL`). Isto traz ONDE ficam as fronteiras, que é outra coisa: é o que
    permite desenhar as zonas em vez de só colorir o número.

    ## A ORDEM dos cortes carrega a direção, e não há campo para ela

    `critical < warn` significa que **menor é pior** — a zona ok fica acima de `warn`.
    `critical > warn` significa que **maior é pior**, e a zona ok fica abaixo. A regra é esta
    frase, e a leitura não é dedução do consumidor: é o contrato dizendo onde fica o bom.

    A segunda versão desta classe tinha um campo `orientation` afirmando a direção, mais um
    validador conferindo que ele concordava com a ordem. Foi removido: a direção é **função
    total** da ordem, então o campo era uma SEGUNDA cópia de um fato que já estava ali, e o
    validador existia só para manter as duas cópias de acordo. Validador que reconcilia duas
    representações do mesmo fato é o sintoma de que a segunda não devia existir — a Regra 14
    pelo avesso. O precedente de `ScaleKind` ("declarada, nunca inferida") não se aplica:
    escala **não** é derivável do dado (`0.8` não diz se a régua é 0..1 ou 0..100); direção é.

    Invariantes:

    1. Os dois cortes são finitos. `inf` não corta nada.
    2. Os dois cortes são **DISTINTOS**. É o invariante que sustenta tudo: com `warn` igual a
       `critical` não há zona do meio *e* a direção fica indeterminada — a régua teria um corte
       só e nada diria de que lado está o ruim. Um corte único é forma legítima que este
       contrato ainda não expressa, e recusá-lo é mais honesto que aceitá-lo sem direção.

    Não há invariante sobre a presença de `value`: o limiar é propriedade da MÉTRICA, não
    desta medição. Medição ausente com limiar publicado é o caso útil — a tela sabe onde
    ficaria o bom, e desenha o vão com as zonas em vez de um traço sem referência.
    """

    #: Fronteira da atenção, na mesma unidade e escala do valor que ela julga.
    warn: float
    #: Fronteira do crítico, na mesma unidade e escala do valor que ela julga.
    #: Comparado a `warn`, é ele que diz de que lado da régua fica o ruim.
    critical: float

    @field_validator("warn", "critical")
    @classmethod
    def _corte_finito(cls, v: float) -> float:
        if not math.isfinite(float(v)):
            raise ValueError("limiar precisa ser finito")
        return float(v)

    @model_validator(mode="after")
    def _cortes_distintos(self) -> PublicThresholds:
        if self.warn == self.critical:
            raise ValueError(
                f"limiares iguais (`{self.warn}`): sem zona do meio, e sem a ordem não há "
                "como saber de que lado da régua fica o ruim"
            )
        return self


class Domain(str, Enum):
    """Procedência SEMÂNTICA. Fechada.

    Não é `source` técnico — `engine.business.cost_estimators…` continua retido, porque
    revela implementação e não acrescenta nada a quem consome. Isto responde outra
    pergunta: *de que domínio veio este número?*

    O discovery levantou o risco: com produtores múltiplos no futuro, o consumidor pareia
    por `id` sem saber se está comparando comportamento com economia. Quatro valores
    resolvem isso sem expor nada.
    """

    SEMANTIC = "semantic"
    BEHAVIORAL = "behavioral"
    STRUCTURAL = "structural"
    ECONOMIC = "economic"


# ═══════════════════════════════════════════════════════════════════════════════════════
# O envelope canônico
# ═══════════════════════════════════════════════════════════════════════════════════════


class PublicMeasurement(ResultV3Model):
    """Uma medição pública: valor separado de disponibilidade, com motivo.

    Invariantes verificados na construção — e cada um existe por um defeito real:

    1. `available` exige valor. Sem isto, "medido" sem número seria representável.
    2. Ausente/não-aplicável/falhou **proíbe** valor. É o absence-as-zero pelo avesso:
       impede um número sobreviver ao lado de um estado que diz que ele não existe.
    3. `partial` exige valor **e** cobertura < 1. Parcial sem cobertura declarada é
       "medido" com uma ressalva que ninguém consegue quantificar.
    4. Ausência **proíbe** `reason=OK`, e `available` **exige** `reason=OK`. `partial` é a
       exceção deliberada: ele tem valor **e** motivo, porque o motivo é o que EXPLICA a
       parcialidade — `missing_dimension` num composto de saúde diz qual peça faltou, e o
       valor continua valendo sobre o que sobrou.

       A primeira versão desta regra dizia `reason == OK` se e somente se há valor, e a
       massa `massa_d_parcial` a derrubou na primeira execução: o composto AI_HEALTH chega
       parcial, com valor e com `missing_dimension`. A regra estava errada, não o dado.
    5. O valor respeita a faixa da escala. `1.4` num `ratio_unit` é erro de montagem, não
       arredondamento.
    """

    id: str = Field(min_length=1)
    value: float | None
    availability: Availability
    reason: Reason
    #: Fração da amostra que sustenta o valor. `None` quando não se aplica.
    data_coverage: float | None = None
    scale: Scale
    #: Versão da fórmula. Obrigatória onde ela pode mudar sem o nome mudar — sem isto,
    #: comparar duas análises longitudinalmente compara coisas diferentes com o mesmo rótulo.
    method_version: str | None = None
    domain: Domain | None = None
    #: Confianca DESTA medicao, quando o produtor a declara.
    #:
    #: **Nao confundir com `global_confidence`**, que e uma SAIDA da analise (#4 do catalogo,
    #: um escore proprio sobre a analise inteira). Este campo e a confianca da medicao
    #: individual — quanta evidencia sustenta ESTE numero.
    #:
    #: Existe porque o `behavior_score` precisava dela SEPARADA do valor. O escore legado
    #: fazia `qualidade x confianca` num so numero, e medido: com comportamento perfeito o
    #: resultado reportava apenas `n/10` (30 com tres conversas, 100 com dez). O consumidor
    #: lia falta de evidencia como baixa qualidade, e a ordenacao chegava a INVERTER.
    #:
    #: `confidence` NUNCA altera `value`. Sao dimensoes distintas da mesma medicao, e fundi-las
    #: e o padrao que o contrato de medicao ja nomeia: "usar uma para mascarar a outra".
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    #: Unidade textual quando a escala não a determina (`duration`, `currency`).
    unit: str | None = None
    #: Os cortes que dividem a régua em ok/atenção/crítico, quando o produtor os declara.
    #:
    #: `None` é o caso majoritário e é honesto: das 39 saídas do catálogo, o motor aplica um
    #: par de limiares a **duas**. Aplicar `75/60` a um custo em dólar ou a uma taxa de
    #: conversão seria inventar semântica que ninguém mediu, e quem decide o "bom" das outras
    #: é produto — não esta camada, que só transporta.
    #:
    #: **Nunca altera `value`.** Mesma regra de `confidence`: o limiar julga o número, não o
    #: modifica. Uma camada que "normalizasse" o valor para caber na zona estaria produzindo
    #: métrica, e nenhuma camada entre o motor e a tela tem autoridade para isso.
    thresholds: PublicThresholds | None = None

    @model_validator(mode="after")
    def _coerencia(self) -> "PublicMeasurement":
        tem_valor = self.value is not None

        if self.availability is Availability.AVAILABLE and not tem_valor:
            raise ValueError(f"`{self.id}`: `available` sem valor")

        if self.availability in (
            Availability.UNAVAILABLE,
            Availability.NOT_EVALUABLE,
            Availability.FAILED,
        ) and tem_valor:
            raise ValueError(
                f"`{self.id}`: `{self.availability.value}` com valor `{self.value}` — "
                "um número ao lado de um estado que diz que ele não existe"
            )

        if self.availability is Availability.PARTIAL:
            if not tem_valor:
                raise ValueError(f"`{self.id}`: `partial` sem valor")
            if self.data_coverage is None or self.data_coverage >= 1.0:
                raise ValueError(
                    f"`{self.id}`: `partial` exige `data_coverage` < 1 — parcial sem "
                    "cobertura declarada é 'medido' com uma ressalva não quantificável"
                )

        if self.availability is Availability.AVAILABLE and self.reason is not Reason.OK:
            raise ValueError(
                f"`{self.id}`: `available` com `reason={self.reason.value}` — medido por "
                "inteiro não tem motivo de ressalva"
            )

        if not tem_valor and self.reason is Reason.OK:
            raise ValueError(
                f"`{self.id}`: sem valor e com `reason=ok` — ausência precisa dizer por quê"
            )

        if self.data_coverage is not None and not (0.0 <= self.data_coverage <= 1.0):
            raise ValueError(f"`{self.id}`: `data_coverage` fora de 0..1")

        faixa = _FAIXAS_CANONICAS.get(self.scale.kind)
        if tem_valor and faixa is not None:
            piso, teto = faixa
            if not (piso <= float(self.value) <= teto):
                raise ValueError(
                    f"`{self.id}`: valor `{self.value}` fora de `{self.scale.kind.value}` "
                    f"({piso}..{teto}) — erro de montagem, não arredondamento"
                )

        # 6. Um corte fora da régua não corta nada. `warn=75` num `ratio_unit` (0..1) deixaria
        #    a zona de atenção inalcançável: a tela desenharia um bullet cuja fronteira fica
        #    fora do próprio eixo, e nenhum valor possível cairia em "atenção". Vale mesmo sem
        #    valor — o limiar é da métrica, e um limiar impossível é erro de montagem hoje,
        #    não quando a primeira medição aparecer.
        if self.thresholds is not None and faixa is not None:
            piso, teto = faixa
            for nome, corte in (
                ("warn", self.thresholds.warn),
                ("critical", self.thresholds.critical),
            ):
                if not (piso <= corte <= teto):
                    raise ValueError(
                        f"`{self.id}`: limiar `{nome}={corte}` fora de "
                        f"`{self.scale.kind.value}` ({piso}..{teto}) — corte fora da régua "
                        "não divide zona nenhuma"
                    )
        return self


# ═══════════════════════════════════════════════════════════════════════════════════════
# As famílias
# ═══════════════════════════════════════════════════════════════════════════════════════


class PublicScore(ResultV3Model):
    """Escore global. Adimensional ou normalizado, nunca por unidade de negócio."""

    measurement: PublicMeasurement
    #: Preenchido só em composto. `ai_health_score` declara as quatro dimensões que o
    #: formam — e é o que impede uma agregação sobre `dimensions[]` somar o agregado junto
    #: das partes.
    composite_of: tuple[str, ...] = ()
    #: Janela metodológica, obrigatória em drift. Drift é medido DENTRO de uma análise;
    #: sem a janela declarada, dois valores de análises diferentes pareceriam série.
    window_kind: str | None = None
    window_size: float | None = None


class PublicIntent(ResultV3Model):
    """Uma intenção, com seu escore e o suporte amostral que o sustenta.

    Achatar isto em `indicators[]` perderia a identidade da intenção: seis intenções
    virariam seis indicadores com ids sintéticos, e a lista de sub-representadas — que o
    relatório do produto já mostra — precisaria de uma segunda estrutura para existir.
    """

    intent_id: str = Field(min_length=1)
    score: PublicMeasurement
    #: Conversas observadas nesta intenção. É o denominador da confiança.
    support: int = Field(ge=0)
    severity: str | None = None
    #: POR QUE o veredito é esse. Códigos do produtor, na ordem em que ele os emitiu.
    #:
    #: **`severity` não é o limiar aplicado ao escore.** Ela é veredito COMPOSTO: o motor a
    #: escala para `WARN` por evidência de mismatch semântico sem olhar a nota. Medido com o
    #: motor real, uma intenção com escore `100` sai `WARN` — e com `score.thresholds`
    #: publicado, `100` cai na zona verde. Sem este campo a tela pinta verde ao lado de um
    #: crachá de atenção e não tem o que dizer.
    #:
    #: **Três estados, e o terceiro é o que impede a tela de mentir por omissão.** `None` =
    #: produtor não declara (motor anterior a esta fatia); `()` = declarou e não há motivo, o
    #: `OK` limpo; preenchido = os códigos. Colapsar `None` em `()` apagaria exatamente o caso
    #: que importa: `severity=WARN` com `[]` só pode vir de produtor antigo, e a tela precisa
    #: poder dizer *"motivo não publicado"* em vez de mostrar atenção sem nada ao lado. É a
    #: regra de omitido × vazio da §4.1 aplicada a um campo, não a uma família.
    #:
    #: Vocabulário aberto, igual ao de `severity`. O consumidor que receber um código que não
    #: sabe traduzir deve MOSTRÁ-LO cru — some da tela é pior que aparecer sem tradução.
    severity_reason: tuple[str, ...] | None = None
    #: Derivado de dado publicado (`support` < `min_samples_per_intent`), não de juízo.
    underrepresented: bool = False

    @model_validator(mode="after")
    def _veredito_ruim_explica_por_que(self) -> PublicIntent:
        """Veredito não-OK com motivo declarado VAZIO é recusado antes do consumidor.

        Não é o mesmo cadeado do fato, e a diferença é o modo de falha que cada um pega: no
        fato, produtor que manda dado incoerente; aqui, MONTAGEM que perde o conteúdo no
        caminho — um `_publicar_intencao` que passasse `()` sobre um fato preenchido produziria
        documento válido pelo schema e mudo na tela.
        """
        if self.severity_reason is None:
            return self
        veredito = (self.severity or "OK").strip().upper()
        if veredito not in {"", "OK"} and not self.severity_reason:
            raise ValueError(
                f"`{self.intent_id}`: `severity={self.severity}` com `severity_reason` vazio — "
                "a tela mostraria atenção sem ter o que explicar"
            )
        return self
    response_variance: PublicMeasurement | None = None
    response_stability: PublicMeasurement | None = None
    #: D4 — dispersao das respostas DENTRO da intencao. MAIOR E PIOR.
    #:
    #: Existe por intencao, e nao so agregado, para a tela destacar a mais problematica e
    #: permitir drill-down. NAO ha campo de "pior drift": ele e derivavel desta lista, e um
    #: campo que duplica um maximo calculavel seria uma segunda verdade sobre o mesmo fato.
    semantic_drift: PublicMeasurement | None = None


class PublicRisk(ResultV3Model):
    """Um risco declarado pelo produtor."""

    id: str = Field(min_length=1)
    measurement: PublicMeasurement
    #: A faixa vem do PRODUTOR ou não vem. Nenhuma camada intermediária a calcula, e o
    #: consumidor não fatia `0..1` por conta própria: escolher onde termina "moderado"
    #: é decisão de produto, e tomá-la na apresentação a esconderia de quem a revisa.
    band: str | None = None


class PublicProjection(ResultV3Model):
    """Uma projeção monetária, com o horizonte como DADO.

    `projected_token_cost@month` e `@year` são a mesma métrica em horizontes diferentes.
    Codificar o horizonte no nome faria quatro métricas onde há duas, e obrigaria o
    consumidor a fazer parsing de identificador para agrupar.
    """

    id: str = Field(min_length=1)
    horizon: str = Field(min_length=1)
    measurement: PublicMeasurement
    currency: str | None = None
    #: Sobre o que a projeção foi feita. Projeção sem base declarada é adivinhação com
    #: casas decimais.
    basis: str | None = None


class MethodMetadata(ResultV3Model):
    """Parâmetros do método, e a moeda da análise.

    `min_samples_per_intent` mora aqui e não em `indicators[]` porque é **configuração**,
    não medida observada. Publicá-lo como indicador o faria parecer algo que a amostra
    revelou.
    """

    min_samples_per_intent: int | None = None
    #: ISO-4217. `None` quando o dataset não declarou — e aí nenhum monetário é publicável.
    currency: str | None = None
    #: Onde a moeda foi declarada. Torna auditável de onde veio a unidade do dinheiro.
    currency_source: str | None = None


# ═══════════════════════════════════════════════════════════════════════════════════════
# O documento
# ═══════════════════════════════════════════════════════════════════════════════════════


class PublicResultV3(ResultV3Model):
    """`analysis-result-v3`.

    Toda família é `None` por default, e a diferença importa: `None` diz que a capacidade
    não existe neste documento; `()` diz que ela existe, executou e não produziu item. Um
    consumidor que vê `alerts: []` sabe que a análise procurou alertas e não achou; um que
    vê o campo ausente sabe que ninguém procurou.
    """

    analysis_id: str = Field(min_length=1)
    result_schema_version: str = RESULT_V3_SCHEMA_VERSION
    indicator_registry_version: str = Field(min_length=1)
    measurement_contract_version: str = Field(min_length=1)
    argos_catalog_version: str = Field(min_length=1)

    summary: PublicSummary
    method: MethodMetadata
    partiality: Partiality

    scores: tuple[PublicScore, ...] | None = None
    dimensions: tuple[PublicMeasurement, ...] | None = None
    indicators: tuple["PublicIndicatorV3", ...] | None = None
    intents: tuple[PublicIntent, ...] | None = None
    risks: tuple[PublicRisk, ...] | None = None
    projections: tuple[PublicProjection, ...] | None = None

    recommendations: tuple[PublicRecommendation, ...] | None = None
    evidence: tuple[PublicEvidenceSummary, ...] | None = None
    alerts: tuple["PublicAlert", ...] | None = None
    issues: tuple["PublicIssue", ...] | None = None
    executive_summary: "PublicExecutiveSummary | None" = None

    @model_validator(mode="after")
    def _identidade_e_unica(self) -> "PublicResultV3":
        for nome, colecao, chave in (
            ("scores", self.scores, lambda s: s.measurement.id),
            ("dimensions", self.dimensions, lambda d: d.id),
            ("indicators", self.indicators, lambda i: i.id),
            ("intents", self.intents, lambda i: i.intent_id),
            ("risks", self.risks, lambda r: r.id),
        ):
            if not colecao:
                continue
            ids = [chave(item) for item in colecao]
            if len(ids) != len(set(ids)):
                raise ValueError(f"`{nome}` tem id repetido — a identidade é a chave")

        if self.projections:
            # Aqui a identidade é o PAR: a mesma métrica em dois horizontes é legítima.
            pares = [(p.id, p.horizon) for p in self.projections]
            if len(pares) != len(set(pares)):
                raise ValueError("`projections` repete o par (id, horizon)")
        return self


class PublicIndicatorV3(ResultV3Model):
    """Indicador de negócio escalar. A forma do v1, mais o que faltava.

    Ganha `reason` (o v1 publicava só `state`, e "não medido" sem motivo não diz a quem lê
    o que fazer), `scale` e `domain`.
    """

    id: str = Field(min_length=1)
    state: IndicatorState
    reason: Reason
    value: float | None
    kind: str
    unit: str | None = None
    currency: str | None = None
    denominator: PublicDenominator | None = None
    coverage: float | None = None
    display_precision: int = 4
    scale: Scale
    domain: Domain | None = None


class PublicAlert(ResultV3Model):
    """Um alerta do ARGOS. A CONTAGEM é métrica (`critical_alert_count`); isto é o conteúdo."""

    id: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    #: Estável, para máquina. O título é para gente e pode mudar de redação.
    code: str = Field(min_length=1)
    title: str = Field(min_length=1)
    detail: str | None = None
    evidence_refs: tuple[str, ...] = ()
    affected_intents: tuple[str, ...] = ()


class PublicIssue(ResultV3Model):
    id: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    code: str = Field(min_length=1)
    title: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()


class PublicExecutiveSummary(ResultV3Model):
    """O resumo executivo, textual.

    `language` é obrigatório: um texto sem idioma declarado não tem como ser apresentado
    honestamente a quem lê noutro, e o `PublicSummary` do v1 — que só tem `analyzed_at` e
    `record_count` — nunca teve onde guardá-lo.
    """

    language: str = Field(min_length=2)
    text: str = Field(min_length=1)
    generated_by: str = "engine"


PublicResultV3.model_rebuild()
