"""Montagem do `analysis-result-v3` — ARGOS completo, e só ARGOS.

## O que este módulo NÃO faz

Não calcula. Não converte escala. Não preenche ausência. Não infere faixa de risco. Não
escolhe moeda. Ele lê fatos declarados e os arruma na forma pública — a mesma disciplina do
`assemble.py` do v1, aplicada a mais famílias.

A tentação nova é a conversão de escala: `response_stability` chega 0..100 e há um
`ratio_unit` logo ao lado. Dividir por 100 aqui seria normalização numérica não autorizada
— e o contrato recusa, porque a escala é declarada no fato e verificada na construção.

## Omitido × vazio, na montagem

Uma família só vira `()` se o produtor a exercitou. Se o fato não a traz, ela sai **ausente**
do documento. É a diferença entre "procurou alertas e não achou" e "ninguém procurou", e ela
precisa nascer aqui: depois de montado, o documento não sabe mais qual das duas era.

`analysis-facts-v1` não carrega scores, intents, risks nem projections. Montar v3 a partir
dele produz um documento sem esses campos — correto, e não vazio.
"""

from __future__ import annotations

from dataclasses import dataclass

from result_assembler.contracts.facts import (
    AnalysisFacts,
    AnalysisFactsV2,
    AnalysisFactsV3,
    Availability,
    FactDimension,
    FactIndicator,
    FactMedida,
    FactThresholds,
)
from result_assembler.contracts.result import (
    IndicatorState,
    Partiality,
    PublicDenominator,
    PublicRecommendation,
    PublicSummary,
)
from result_assembler.contracts.result_v3 import (
    RESULT_V3_SCHEMA_VERSION,
    Domain,
    PublicAlert,
    PublicEvidenceSummaryV3,
    PublicExecutiveSummary,
    PublicIssue,
    MethodMetadata,
    PublicIndicatorV3,
    PublicIntent,
    PublicMeasurement,
    PublicProjection,
    PublicResultV3,
    PublicRisk,
    PublicScore,
    PublicThresholds,
    Scale,
    ScaleKind,
)
from result_assembler.errors import UnknownIndicator
from result_assembler.validation.invariants import validate_facts
from result_assembler.validation.safety import validate_evidence_safety
from result_assembler.registry.argos_catalog import ARGOS_CATALOG_VERSION, POR_ID, Familia
from result_assembler.registry.indicators import (
    INDICATOR_REGISTRY_VERSION_V3,
    CANONICAL_ORDER_V3,
    definicao_de,
)

#: Disponibilidade do fato → estado público do indicador. Igual ao v1, de propósito: o
#: vocabulário público não muda por causa de uma versão nova de documento.
_ESTADO_PUBLICO: dict[Availability, IndicatorState] = {
    Availability.AVAILABLE: IndicatorState.MEASURED,
    Availability.PARTIAL: IndicatorState.PARTIALLY_MEASURED,
    Availability.UNAVAILABLE: IndicatorState.NOT_MEASURED,
    Availability.NOT_EVALUABLE: IndicatorState.NOT_APPLICABLE,
    Availability.FAILED: IndicatorState.CALCULATION_FAILED,
}

_MOTIVO_POR_ESTADO: dict[IndicatorState, str] = {
    IndicatorState.PARTIALLY_MEASURED: "indicator_partially_measured",
    IndicatorState.NOT_MEASURED: "indicator_not_measured",
    IndicatorState.NOT_APPLICABLE: "indicator_not_applicable",
    IndicatorState.CALCULATION_FAILED: "indicator_calculation_failed",
}

#: `kind` do registro → escala pública. Mapa FECHADO: um kind novo sem escala declarada
#: para a montagem em vez de escolher `raw` por omissão, que seria o assembler decidindo o
#: que o contrato deve dizer sobre um número.
_ESCALA_POR_KIND: dict[str, ScaleKind] = {
    "ratio": ScaleKind.RATIO_UNIT,
    "count": ScaleKind.COUNT,
    "currency": ScaleKind.CURRENCY,
    "scalar": ScaleKind.RAW,
}

#: As quatro dimensões de saúde são `ratio_unit` por contrato do composto (F2.5).
_ESCALA_DIMENSAO = Scale(kind=ScaleKind.RATIO_UNIT)


class EscalaNaoDeclarada(ValueError):
    """Um `kind` chegou sem escala pública correspondente.

    Recusar é a decisão certa: publicar `raw` por omissão faria o assembler escolher o que
    o contrato afirma sobre a faixa de um número, que é exatamente o tipo de decisão que
    ele não toma.
    """


@dataclass(frozen=True)
class AssemblyV3Outcome:
    public_result: PublicResultV3


def _escala_de(kind: str) -> Scale:
    escala = _ESCALA_POR_KIND.get(kind)
    if escala is None:
        raise EscalaNaoDeclarada(f"`{kind}` não tem escala pública declarada")
    return Scale(kind=escala)


def _dominio_de(public_id: str) -> Domain | None:
    """A procedência semântica, quando o catálogo a conhece.

    Só as quatro dimensões de saúde a declaram hoje — elas SÃO os domínios. Para o resto o
    campo sai `None`, que é honesto: inventar um domínio para `useful_outcome_rate` seria
    afirmar uma classificação que ninguém fez.
    """
    entrada = POR_ID.get(public_id)
    if entrada is None or entrada.familia is not Familia.DIMENSIONS:
        return None
    return Domain(entrada.public_id)


def _publicar_indicador(ind: FactIndicator) -> PublicIndicatorV3:
    defin = definicao_de(ind.id)
    if defin is None:  # pragma: no cover - `validate_facts` recusa antes de chegar aqui
        raise UnknownIndicator("indicador não registrado")

    estado = _ESTADO_PUBLICO[ind.availability]
    denom = (
        PublicDenominator(kind=ind.denominator.kind, value=ind.denominator.value)
        if ind.denominator is not None
        else None
    )
    return PublicIndicatorV3(
        id=defin.public_id,
        state=estado,
        # O v1 retinha o motivo. Publicá-lo é o que transforma "não medido" — que não diz a
        # quem lê o que fazer — em "custo indisponível: moeda não declarada".
        reason=ind.reason,
        value=ind.value,
        kind=defin.kind.value,
        unit=defin.unit,
        currency=ind.currency,
        denominator=denom,
        coverage=ind.data_coverage if estado is IndicatorState.PARTIALLY_MEASURED else None,
        display_precision=defin.display_precision,
        scale=_escala_de(defin.kind.value),
        domain=_dominio_de(defin.public_id),
    )


def _publicar_dimensao(dim: FactDimension) -> PublicMeasurement:
    """A dimensão vira `PublicMeasurement`, não um tipo próprio.

    Ela É uma medição de saúde: valor, disponibilidade, motivo e cobertura. Ter um tipo
    separado, como no v1, obrigava a duplicar os invariantes — e foi por não tê-los que o
    v1 pôde publicar dimensão sem motivo.
    """
    return PublicMeasurement(
        id=dim.id,
        value=dim.value,
        availability=dim.availability,
        reason=dim.reason,
        data_coverage=dim.data_coverage,
        scale=_ESCALA_DIMENSAO,
        domain=_dominio_de(dim.id),
    )


def _ordem_canonica(facts: AnalysisFacts) -> tuple[FactIndicator, ...]:
    """Ordem CONTRATADA, não a de chegada — senão o checksum vira função de quem montou."""
    por_id = {ind.id: ind for ind in facts.indicators}
    # A ordem do v3 DERIVA da do v1: os catorze primeiro, na mesma sequencia, e o
    # que estreou no v3 depois. Indicador antigo nunca muda de posicao.
    return tuple(por_id[i] for i in CANONICAL_ORDER_V3 if i in por_id)


def _partialidade(indicadores: tuple[PublicIndicatorV3, ...]) -> Partiality:
    motivos = {_MOTIVO_POR_ESTADO[i.state] for i in indicadores if i.state in _MOTIVO_POR_ESTADO}
    return Partiality(complete=not motivos, reasons=tuple(sorted(motivos)))


def _moeda_declarada(indicadores: tuple[PublicIndicatorV3, ...]) -> str | None:
    """A moeda da análise, LIDA dos fatos monetários. Não é escolha do assembler.

    Ela já viajou junto do valor desde o dataset; aqui só é promovida ao cabeçalho para o
    consumidor não precisar varrer indicadores para descobrir em que unidade está o
    dinheiro. Divergência entre indicadores seria contradição no fato — e o produtor já a
    recusa antes, porque a unidade é declarada uma vez por dataset.
    """
    moedas = {i.currency for i in indicadores if i.currency}
    return next(iter(moedas)) if len(moedas) == 1 else None


def _publicar_familias_analiticas(facts: AnalysisFacts) -> dict[str, object]:
    """As familias que so o `analysis-facts-v2` carrega.

    Fatos v1 nao as declaram — nem vazias. Devolver `{}` faz os campos sairem AUSENTES do
    documento, que e o que "ninguem produziu" quer dizer. Se um dia alguem trocar isto por
    `()`, o consumidor passa a ler "procuramos alertas e nao achamos" sobre uma analise que
    nunca procurou.
    """
    if not isinstance(facts, AnalysisFactsV2):
        return {}

    saida: dict[str, object] = {}
    if facts.alerts is not None:
        saida["alerts"] = tuple(
            PublicAlert(
                id=a.id, severity=a.severity, code=a.code, title=a.title,
                detail=a.detail, evidence_refs=a.evidence_refs,
                affected_intents=a.affected_intents,
            )
            for a in facts.alerts
        )
    if facts.issues is not None:
        saida["issues"] = tuple(
            PublicIssue(
                id=i.id, severity=i.severity, code=i.code, title=i.title,
                evidence_refs=i.evidence_refs,
            )
            for i in facts.issues
        )
    if facts.executive_summary is not None:
        resumo = facts.executive_summary
        saida["executive_summary"] = PublicExecutiveSummary(
            language=resumo.language, text=resumo.text, generated_by=resumo.generated_by
        )
    return saida


#: A escala das saídas que NÃO são indicador, declarada por id público.
#:
#: Os indicadores tiram a escala do `kind` da definição no registro; as famílias
#: quantitativas não têm `kind`, e deixá-las herdar uma escala por família estaria errado:
#: os sete escores do catálogo não vivem todos na mesma faixa. Então é por id, e a busca
#: falha FECHADA — id sem escala declarada levanta em vez de publicar medição sem faixa.
_ESCALA_POR_SAIDA: dict[str, Scale] = {
    # A escala e a DO PRODUTOR, medida no retorno do motor — nao a que o nome sugere.
    # `measurements.ai_health` vive em 0..1 (medido: 0.7621), e o legado
    # `business_impact.ai_health_score` e o MESMO numero vezes 100. Publicar o composto
    # honesto sob `score_100` faria 0.76 ser lido como saude pessima; multiplica-lo por 100
    # seria normalizacao nao autorizada, que e o que a docstring do `ScaleKind` proibe.
    "ai_health_score": Scale(kind=ScaleKind.RATIO_UNIT),
    # `intent_score` fica declarado porque o catalogo o declara (#15) — e hoje chega
    # `unavailable`: o motor produz variancia, estabilidade, suporte e severidade por
    # intencao, nao um escore composto dela. A escala existe para quando existir produtor.
    "intent_score": Scale(kind=ScaleKind.SCORE_100),
    # 0..100 do produtor (`response_stability_score`), publicado como tal.
    "response_stability": Scale(kind=ScaleKind.SCORE_100),
    # Probabilidades. A `band` é do produtor; a faixa numérica é do contrato.
    "containment_risk": Scale(kind=ScaleKind.RATIO_UNIT),
    "conversion_risk": Scale(kind=ScaleKind.RATIO_UNIT),
    # Dinheiro: faixa ABERTA de propósito. Custo não tem teto contratável, e a unidade vem
    # da moeda, não da escala.
    "projected_token_cost": Scale(kind=ScaleKind.CURRENCY),
    "projected_handoff_cost": Scale(kind=ScaleKind.CURRENCY),
    # `raw` é a resposta honesta enquanto a faixa for decisão de produto em aberto: é a
    # única medida do catálogo em que MAIOR é PIOR, e inventar um teto aqui inverteria a
    # leitura de quem desenha a barra.
    "response_variance": Scale(kind=ScaleKind.RAW),
    # D4 — os quatro que ganharam envelope Measurement. Faixas MEDIDAS no motor:
    # `governance_score` (que e o `consistency_score` agregado) nao passa de 100 por
    # construcao — a config normaliza `W_LEN + W_SIM = 1` e os dois componentes sao
    # limitados a 100. `confidence` e `min(1.0, n/full_at_n)`.
    # D5 — a metrica-mae. `max(0, raw_governance_score - cross_intent_penalty)` vive em
    # 0..100, como o `consistency_score`. A spec dizia `ratio_unit`, palpite feito quando ela
    # nao tinha produtor: publicar 47.25 sob `ratio_unit` faria o invariante de faixa LEVANTAR.
    "behavior_score": Scale(kind=ScaleKind.SCORE_100),
    "consistency_score": Scale(kind=ScaleKind.SCORE_100),
    "global_confidence": Scale(kind=ScaleKind.RATIO_UNIT),
    "cross_intent_similarity": Scale(kind=ScaleKind.RATIO_UNIT),
    # MAIOR E PIOR — a segunda do catalogo nessa direcao, ao lado de `response_variance`.
    # `clamp(1 - mean_answer_similarity, 0, 1)` garante a faixa.
    "semantic_drift": Scale(kind=ScaleKind.RATIO_UNIT),
}


def _escala_da_saida(public_id: str) -> Scale:
    escala = _ESCALA_POR_SAIDA.get(public_id)
    if escala is None:
        raise EscalaNaoDeclarada(f"`{public_id}` não tem escala pública declarada")
    return escala


def _publicar_limiar(limiar: FactThresholds | None) -> PublicThresholds | None:
    """`FactThresholds` → `PublicThresholds`, campo a campo e sem conta.

    Existe como função em vez de expressão inline porque a AUSÊNCIA precisa atravessar como
    ausência. Um `PublicThresholds(...)` construído sempre, com zeros no lugar do que não
    veio, publicaria `warn=0` — que nesta escala é a fronteira mais severa possível — para as
    36 saídas a que o motor não aplica limiar nenhum. É o absence-as-zero na sua forma mais
    cara: não some da tela, aparece como alarme.

    A conversão é campo a campo e sem conta. **A ordem é preservada**, e isso não é detalhe de
    transporte: é a ordem que diz de que lado da régua fica o ruim, então trocar `warn` por
    `critical` aqui inverteria as zonas na tela sem mudar nenhum número. Os dois modelos
    recusam cortes iguais, cada um na sua fronteira.
    """
    if limiar is None:
        return None
    return PublicThresholds(warn=limiar.warn, critical=limiar.critical)


def _publicar_medida(m: FactMedida) -> PublicMeasurement:
    """`FactMedida` → `PublicMeasurement`, com a escala vinda do registro.

    Nenhum número é recalculado, convertido ou completado: o valor sai como o produtor o
    mediu. O que esta função acrescenta é a FAIXA, que o produtor não declara — e é por
    isso que ela mora aqui e não no fato.

    O LIMIAR é o contrário da faixa: ele vem do produtor ou não vem. A faixa é propriedade da
    régua e esta camada a conhece pelo registro; onde começa o "bom" é juízo de quem mediu, e
    uma camada de transporte que o inventasse estaria produzindo métrica.
    """
    return PublicMeasurement(
        id=m.id,
        value=m.value,
        availability=m.availability,
        reason=m.reason,
        data_coverage=m.data_coverage,
        scale=_escala_da_saida(m.id),
        # D5 — dimensao PROPRIA, nunca dentro do valor.
        confidence=m.confidence,
        method_version=m.calculation_version,
        domain=_dominio_de(m.id),
        thresholds=_publicar_limiar(m.thresholds),
    )


def _publicar_familias_quantitativas(
    facts: AnalysisFacts, *, min_samples: int | None
) -> dict[str, object]:
    """As famílias que só o `analysis-facts-v3` carrega.

    Mesma disciplina de `_publicar_familias_analiticas`: fato que não as declara sai sem os
    campos, porque "ninguém produziu" e "produziu e não achou" são estados diferentes.
    """
    if not isinstance(facts, AnalysisFactsV3):
        return {}

    saida: dict[str, object] = {}

    if facts.scores is not None:
        saida["scores"] = tuple(
            PublicScore(
                measurement=_publicar_medida(s),
                composite_of=s.composite_of,
                window_kind=s.window_kind,
                window_size=s.window_size,
            )
            for s in facts.scores
        )

    if facts.risks is not None:
        saida["risks"] = tuple(
            PublicRisk(id=r.id, measurement=_publicar_medida(r), band=r.band)
            for r in facts.risks
        )

    if facts.projections is not None:
        saida["projections"] = tuple(
            PublicProjection(
                id=p.id,
                horizon=p.horizon,
                measurement=_publicar_medida(p),
                currency=p.currency,
                basis=p.basis,
            )
            for p in facts.projections
        )

    if facts.intents is not None:
        saida["intents"] = tuple(
            PublicIntent(
                intent_id=i.intent_id,
                score=_publicar_medida(i.score),
                support=i.support,
                severity=i.severity,
                # Atravessa como veio, com os TRÊS estados preservados. `None` (produtor não
                # declara) não pode virar `()` (declarou e não há motivo): é a diferença entre
                # "motivo não publicado" e "sem motivo", e só a primeira explica um crachá de
                # atenção sem texto ao lado.
                severity_reason=i.severity_reason,
                # DERIVADO aqui, e não recebido pronto: `support` e `min_samples_per_intent`
                # são ambos publicados, então o consumidor pode refazer a conta. Receber o
                # booleano do produtor criaria uma segunda verdade que ninguém consegue
                # conferir. Sem limiar declarado não há sub-representação a afirmar.
                underrepresented=(min_samples is not None and i.support < min_samples),
                response_variance=(
                    _publicar_medida(i.response_variance)
                    if i.response_variance is not None
                    else None
                ),
                response_stability=(
                    _publicar_medida(i.response_stability)
                    if i.response_stability is not None
                    else None
                ),
                semantic_drift=(
                    _publicar_medida(i.semantic_drift)
                    if i.semantic_drift is not None
                    else None
                ),
            )
            for i in facts.intents
        )

    return saida


def _min_samples_de(facts: AnalysisFacts) -> int | None:
    """O limiar do método, quando o fato o declara."""
    if not isinstance(facts, AnalysisFactsV3) or facts.method is None:
        return None
    return facts.method.min_samples_per_intent


def assemble_v3(facts: AnalysisFacts) -> AssemblyV3Outcome:
    """`analysis-facts-*` → `analysis-result-v3`.

    Famílias que o fato não traz saem AUSENTES do documento, não vazias. Montar a partir de
    `analysis-facts-v1` — que não carrega scores, intents, risks nem projections — produz um
    v3 sem esses campos, e isso é a resposta correta: ninguém os produziu.
    """
    validate_facts(facts)
    # A REDE DE CONTEUDO, e ela NAO estava ligada aqui.
    #
    # `assemble` (v1) e `assemble_v2` chamam `validate_evidence_safety` desde que ela existe. O
    # v3 — que e o caminho de producao — chamava so `validate_facts`, que verifica INVARIANTES
    # (referencia de evidencia, coerencia de familia), nao CONTEUDO.
    #
    # Resultado: a unica montagem viva era a unica sem varredura. A rede existia, tinha teste,
    # e nao cobria nada do que sai.
    validate_evidence_safety(facts)
    min_samples = _min_samples_de(facts)
    indicadores = tuple(_publicar_indicador(i) for i in _ordem_canonica(facts))
    dimensoes = tuple(_publicar_dimensao(d) for d in facts.dimensions)

    recomendacoes = tuple(
        PublicRecommendation(
            id=r.id,
            title=r.title,
            priority=r.priority,
            category=r.category,
            evidence_refs=r.evidence_refs,
        )
        for r in sorted(facts.recommendations, key=lambda r: r.order)
    )
    evidencias = tuple(
        # O TRECHO atravessa. Campo a campo, e nao por `model_dump`: a allowlist so e allowlist
        # enquanto alguem precisar ESCREVER cada campo aqui. Um campo novo no fato que chegasse
        # ao publico por copia seria a allowlist virando denylist sem ninguem decidir.
        PublicEvidenceSummaryV3(
            id=e.id,
            kind=e.kind,
            observed_count=e.observed_count,
            label=e.label,
            excerpt=e.excerpt,
        )
        for e in facts.evidence
    )

    publico = PublicResultV3(
        analysis_id=facts.identity.analysis_id,
        result_schema_version=RESULT_V3_SCHEMA_VERSION,
        indicator_registry_version=INDICATOR_REGISTRY_VERSION_V3,
        measurement_contract_version=facts.measurement_contract_version,
        argos_catalog_version=ARGOS_CATALOG_VERSION,
        summary=PublicSummary(
            record_count=facts.window.record_count,
            analyzed_at=facts.window.analyzed_at,
        ),
        method=MethodMetadata(
            currency=_moeda_declarada(indicadores),
            min_samples_per_intent=min_samples,
        ),
        partiality=_partialidade(indicadores),
        indicators=indicadores,
        # `or None`: um fato sem dimensão nenhuma não exercitou a capacidade, e `()` diria
        # que exercitou e não achou. A distinção morre se não nascer aqui.
        dimensions=dimensoes or None,
        recommendations=recomendacoes or None,
        evidence=evidencias or None,
        **_publicar_familias_analiticas(facts),
        **_publicar_familias_quantitativas(facts, min_samples=min_samples),
    )
    return AssemblyV3Outcome(public_result=publico)
