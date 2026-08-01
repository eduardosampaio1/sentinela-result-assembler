"""Invariantes dos fatos. Fail-closed: a primeira violação recusa a montagem.

A ordem das verificações é fixa e vai do envelope para o detalhe. Isso não é estética:
com ordem fixa, a mesma entrada inválida produz sempre o MESMO erro — o consumidor pode
tratar programaticamente em vez de reagir a uma mensagem que muda.

Nenhuma mensagem carrega valor medido, texto de recomendação ou conteúdo de evidência.
A localização (`indicators[3].value`) basta para depurar sem virar vazamento em log.
"""

from __future__ import annotations

import math

from result_assembler.contracts.facts import (
    AnalysisFacts,
    Availability,
    FactIndicator,
    IndicatorKind,
    Reason,
)
from result_assembler.errors import (
    AssemblyInvariantViolation,
    DuplicateIndicator,
    InvalidDenominator,
    InvalidUnit,
    InvalidValue,
    MissingRequiredFact,
    UnknownIndicator,
    UnsupportedFactsVersion,
    UnsupportedMeasurementVersion,
)
from result_assembler.registry.indicators import (
    SUPPORTED_DIMENSION_CALCULATION_VERSIONS,
    SUPPORTED_DIMENSION_IDS,
    SUPPORTED_DIMENSION_SOURCES,
    IndicatorDefinition,
    definicao_de,
)
from result_assembler.version import (
    SUPPORTED_FACTS_SCHEMA_VERSIONS,
    SUPPORTED_MEASUREMENT_CONTRACT_VERSIONS,
)

#: Estados em que um valor numérico PRECISA estar presente.
_COM_VALOR = frozenset({Availability.AVAILABLE, Availability.PARTIAL})


def _validar_versoes(facts: AnalysisFacts) -> None:
    if facts.facts_schema_version not in SUPPORTED_FACTS_SCHEMA_VERSIONS:
        raise UnsupportedFactsVersion(
            "versão de facts não suportada", location="facts_schema_version"
        )
    if facts.measurement_contract_version not in SUPPORTED_MEASUREMENT_CONTRACT_VERSIONS:
        raise UnsupportedMeasurementVersion(
            "versão do contrato de medição não suportada",
            location="measurement_contract_version",
        )


def _validar_identidade(facts: AnalysisFacts) -> None:
    if not facts.identity.analysis_id.strip():
        raise MissingRequiredFact("analysis_id vazio", location="identity.analysis_id")
    if not facts.window.analyzed_at.strip():
        # O assembler não tem relógio: sem esta data não existe resultado honesto.
        raise MissingRequiredFact("analyzed_at ausente", location="window.analyzed_at")


def _validar_coerencia_disponibilidade(ind: FactIndicator, onde: str) -> None:
    """Disponibilidade e valor não podem se contradizer."""
    tem_valor = ind.value is not None
    if ind.availability in _COM_VALOR and not tem_valor:
        raise AssemblyInvariantViolation(
            f"availability={ind.availability.value} exige valor presente", location=onde
        )
    if ind.availability not in _COM_VALOR:
        if tem_valor:
            # Este é o defeito clássico: ausência publicada como 0.0. Vale a pena o erro
            # dedicado — "unavailable com value=0.0" costuma ser lido como zero real.
            raise AssemblyInvariantViolation(
                f"availability={ind.availability.value} exige valor ausente; "
                "ausência NÃO pode ser representada por zero",
                location=f"{onde}.value",
            )
        if ind.reason.value == "ok":
            raise AssemblyInvariantViolation(
                "indisponibilidade exige motivo diferente de 'ok'", location=f"{onde}.reason"
            )
    if ind.availability is Availability.PARTIAL:
        cob = ind.data_coverage
        if cob is None or not (0.0 < cob < 1.0):
            raise AssemblyInvariantViolation(
                "partial exige data_coverage estritamente entre 0 e 1",
                location=f"{onde}.data_coverage",
            )
    elif (
        ind.availability is Availability.AVAILABLE
        and ind.data_coverage is not None
        and ind.data_coverage != 1.0
    ):
        raise AssemblyInvariantViolation(
            "available com cobertura declarada exige data_coverage=1.0",
            location=f"{onde}.data_coverage",
        )
    _validar_unidades_observadas(ind, onde)


def _validar_unidades_observadas(ind: FactIndicator, onde: str) -> None:
    """`observed_units`/`expected_units` precisam ser coerentes entre si e com a cobertura.

    Sem esta checagem (Codex R1 [3]), um produtor poderia declarar `data_coverage=0.5`
    com `observed=25` e `expected=1000` e ninguém notaria — a cobertura publicada estaria
    contando uma história que os próprios contadores desmentem.
    """
    # `observed_units >= 0` e `expected_units > 0` são restrições do Field (e portanto
    # do JSON Schema publicado). O que sobra aqui é o que só se vê com os dois juntos.
    obs, esp = ind.observed_units, ind.expected_units
    if obs is None or esp is None:
        return
    if obs > esp:
        raise AssemblyInvariantViolation(
            "observed_units não pode exceder expected_units", location=onde
        )
    # Tolerância de 0.01 porque a cobertura costuma vir arredondada pelo produtor.
    if ind.data_coverage is not None and abs((obs / esp) - ind.data_coverage) > 0.01:
        raise AssemblyInvariantViolation(
            "data_coverage não corresponde a observed_units/expected_units",
            location=f"{onde}.data_coverage",
        )


def _validar_contra_definicao(
    ind: FactIndicator, defin: IndicatorDefinition, onde: str
) -> None:
    if ind.kind is not defin.kind:
        raise InvalidValue(
            f"kind incompatível: contrato exige {defin.kind.value}", location=f"{onde}.kind"
        )
    if ind.calculation_version not in defin.accepted_calculation_versions:
        raise UnsupportedMeasurementVersion(
            "calculation_version fora das versões aceitas para este indicador",
            location=f"{onde}.calculation_version",
        )
    if ind.source not in defin.accepted_sources:
        raise InvalidValue(
            "source não é uma origem analítica aceita para este indicador",
            location=f"{onde}.source",
        )
    if ind.availability not in defin.allowed_availability:
        raise AssemblyInvariantViolation(
            "availability não permitida para este indicador", location=f"{onde}.availability"
        )
    # A unidade é OBRIGATÓRIA quando o registro contrata uma, e proibida quando não.
    # Aceitar `unit` ausente (Codex R1 [2]) deixaria o produtor omitir a declaração e o
    # fato passaria "como se" a unidade tivesse sido confirmada — que é o oposto do
    # objetivo: o contrato existe para o produtor DIZER o que mediu.
    if defin.unit is None:
        if ind.unit is not None:
            raise InvalidUnit(
                "indicador não contrata unidade", location=f"{onde}.unit"
            )
    elif ind.unit is None:
        raise InvalidUnit(
            f"unidade obrigatória para este indicador ('{defin.unit}')",
            location=f"{onde}.unit",
        )
    elif ind.unit != defin.unit:
        raise InvalidUnit("unidade diverge da contratada", location=f"{onde}.unit")

    # Denominador: exigido só quando o indicador tem valor. Sem valor não há razão a
    # auditar, e exigir denominador de algo não medido seria burocracia sem verdade.
    if ind.value is not None:
        if defin.denominator_kind is not None:
            if ind.denominator is None:
                raise InvalidDenominator(
                    "indicador exige denominador quando há valor", location=f"{onde}.denominator"
                )
            if ind.denominator.kind != defin.denominator_kind:
                raise InvalidDenominator(
                    f"denominador precisa ser '{defin.denominator_kind}'",
                    location=f"{onde}.denominator.kind",
                )
        elif ind.denominator is not None:
            raise InvalidDenominator(
                "indicador não contrata denominador", location=f"{onde}.denominator"
            )

        valor = float(ind.value)
        if not math.isfinite(valor):
            raise InvalidValue("valor não finito", location=f"{onde}.value")
        if defin.valid_range is not None:
            baixo, alto = defin.valid_range
            if not (baixo <= valor <= alto):
                # Cobre razão fora de [0,1] E contagem negativa — mesma regra, uma faixa.
                raise InvalidValue(
                    f"valor fora da faixa contratada [{baixo}, {alto}]", location=f"{onde}.value"
                )
        if defin.kind is IndicatorKind.COUNT and valor != int(valor):
            raise InvalidValue("contagem precisa ser inteira", location=f"{onde}.value")
        if defin.kind is IndicatorKind.CURRENCY:
            # Valor monetário sem código de moeda é ambíguo por natureza: 0.125 em BRL e
            # em USD são números iguais e fatos diferentes. O contrato exige o código.
            if not ind.currency:
                raise InvalidUnit(
                    "indicador monetário com valor exige código de moeda",
                    location=f"{onde}.currency",
                )
            if len(ind.currency) != 3 or not ind.currency.isupper() or not ind.currency.isalpha():
                raise InvalidUnit(
                    "código de moeda precisa ser ISO-4217 (3 letras maiúsculas)",
                    location=f"{onde}.currency",
                )
    elif ind.currency:
        raise InvalidUnit(
            "código de moeda declarado sem valor medido", location=f"{onde}.currency"
        )


def _validar_indicadores(facts: AnalysisFacts) -> None:
    vistos: set[str] = set()
    for i, ind in enumerate(facts.indicators):
        onde = f"indicators[{i}]"
        if ind.id in vistos:
            raise DuplicateIndicator(f"id repetido: {ind.id}", location=onde)
        vistos.add(ind.id)

        defin = definicao_de(ind.id)
        if defin is None:
            # Fail-closed. Aceitar um objeto arbitrário aqui é como o contrato morre:
            # um campo novo do domínio viraria indicador público sem ninguém decidir.
            raise UnknownIndicator(f"indicador não registrado: {ind.id}", location=onde)

        _validar_coerencia_disponibilidade(ind, onde)
        _validar_contra_definicao(ind, defin, onde)


def _validar_dimensoes(facts: AnalysisFacts) -> None:
    """Dimensões passam pela MESMA régua dos indicadores.

    Codex R1 [1]: elas não passavam por régua nenhuma. Uma dimensão `unavailable`
    carregando `value=0.72` atravessava e era publicada com `state="not_measured"` e valor
    presente — o defeito "ausência com valor" que os indicadores já bloqueavam, entrando
    pela porta ao lado. `calculation_version` também não era verificada.
    """
    vistas: set[str] = set()
    for i, dim in enumerate(facts.dimensions):
        onde = f"dimensions[{i}]"
        if dim.id not in SUPPORTED_DIMENSION_IDS:
            raise UnknownIndicator(f"dimensão não registrada: {dim.id}", location=onde)
        if dim.id in vistas:
            raise DuplicateIndicator(f"dimensão repetida: {dim.id}", location=onde)
        vistas.add(dim.id)

        if dim.calculation_version not in SUPPORTED_DIMENSION_CALCULATION_VERSIONS:
            raise UnsupportedMeasurementVersion(
                "calculation_version fora das versões aceitas para dimensões",
                location=f"{onde}.calculation_version",
            )
        if dim.source not in SUPPORTED_DIMENSION_SOURCES:
            raise InvalidValue(
                "source não é uma origem analítica aceita para dimensões",
                location=f"{onde}.source",
            )

        tem_valor = dim.value is not None
        if dim.availability in _COM_VALOR and not tem_valor:
            raise AssemblyInvariantViolation(
                f"availability={dim.availability.value} exige valor presente", location=onde
            )
        if dim.availability not in _COM_VALOR:
            if tem_valor:
                raise AssemblyInvariantViolation(
                    f"availability={dim.availability.value} exige valor ausente; "
                    "ausência NÃO pode ser representada por zero",
                    location=f"{onde}.value",
                )
            if dim.reason is Reason.OK:
                raise AssemblyInvariantViolation(
                    "indisponibilidade exige motivo diferente de 'ok'",
                    location=f"{onde}.reason",
                )
        if dim.availability is Availability.PARTIAL:
            if dim.data_coverage is None or not (0.0 < dim.data_coverage < 1.0):
                raise AssemblyInvariantViolation(
                    "partial exige data_coverage estritamente entre 0 e 1",
                    location=f"{onde}.data_coverage",
                )
        elif dim.data_coverage is not None and dim.data_coverage != 1.0:
            raise AssemblyInvariantViolation(
                "cobertura declarada fora de partial exige data_coverage=1.0",
                location=f"{onde}.data_coverage",
            )


def _validar_recomendacoes(facts: AnalysisFacts) -> None:
    ids: set[str] = set()
    ordens: set[int] = set()
    evidencias = {e.id for e in facts.evidence}
    for i, rec in enumerate(facts.recommendations):
        onde = f"recommendations[{i}]"
        if rec.id in ids:
            raise AssemblyInvariantViolation(f"recomendação repetida: {rec.id}", location=onde)
        ids.add(rec.id)
        if rec.order in ordens:
            # Ordem repetida tornaria a publicação dependente da ordem de chegada — e aí
            # o mesmo fato geraria bytes diferentes.
            raise AssemblyInvariantViolation(
                f"ordem repetida: {rec.order}", location=f"{onde}.order"
            )
        ordens.add(rec.order)
        if not rec.priority.strip():
            raise AssemblyInvariantViolation("prioridade ausente", location=f"{onde}.priority")
        for ref in rec.evidence_refs:
            if ref not in evidencias:
                raise AssemblyInvariantViolation(
                    f"evidence_ref sem evidência correspondente: {ref}",
                    location=f"{onde}.evidence_refs",
                )


def _validar_evidencias(facts: AnalysisFacts) -> None:
    ids: set[str] = set()
    for i, ev in enumerate(facts.evidence):
        onde = f"evidence[{i}]"
        if ev.id in ids:
            raise AssemblyInvariantViolation(f"evidência repetida: {ev.id}", location=onde)
        ids.add(ev.id)


def validate_facts(facts: AnalysisFacts) -> None:
    """Aplica todos os invariantes. Levanta na primeira violação; devolve `None` se passa."""
    _validar_versoes(facts)
    _validar_identidade(facts)
    _validar_indicadores(facts)
    _validar_dimensoes(facts)
    _validar_recomendacoes(facts)
    _validar_evidencias(facts)
