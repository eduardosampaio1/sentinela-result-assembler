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

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    #: Unidade textual quando a escala não a determina (`duration`, `currency`).
    unit: str | None = None

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
    #: Derivado de dado publicado (`support` < `min_samples_per_intent`), não de juízo.
    underrepresented: bool = False
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
