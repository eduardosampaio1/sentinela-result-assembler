"""Erros públicos da biblioteca.

Regra de ouro: a mensagem NUNCA contém o payload bruto. Ela contém uma **localização
segura** — em que seção, em que índice, em que campo, e (quando o dado já é público por
natureza, como o id de um indicador) qual identificador. Valores medidos, textos de
recomendação, evidências e metadados internos ficam de fora: uma exceção costuma acabar
em log, e log é o vazamento mais fácil de esquecer.

`category` é o código estável para máquina; a classe é o tipo para `except`.
"""

from __future__ import annotations


class AssemblyError(Exception):
    """Raiz de tudo que o assembler recusa. Consumidores podem capturar só esta."""

    #: Código estável, para máquina. Sobrescrito por cada subclasse.
    category = "assembly_error"

    def __init__(self, message: str, *, location: str = "") -> None:
        self.location = location
        completo = f"{message} [em {location}]" if location else message
        super().__init__(completo)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return super().__str__()


class UnsupportedFactsVersion(AssemblyError):
    """`facts_schema_version` não é uma versão que este assembler sabe ler."""

    category = "unsupported_facts_version"


class UnsupportedMeasurementVersion(AssemblyError):
    """`measurement_contract_version` fora da lista suportada.

    Recusa deliberada: montar um resultado público sob semântica de medição desconhecida
    é pior do que não montar — o consumidor não teria como saber que o significado mudou.
    """

    category = "unsupported_measurement_version"


class UnknownIndicator(AssemblyError):
    """Indicador que não está no registro canônico. Fail-closed por padrão."""

    category = "unknown_indicator"


class InvalidUnit(AssemblyError):
    """Unidade declarada nos fatos diverge da unidade contratada para o indicador."""

    category = "invalid_unit"


class InvalidDenominator(AssemblyError):
    """Denominador ausente quando obrigatório, ou incompatível com o contratado."""

    category = "invalid_denominator"


class InvalidValue(AssemblyError):
    """Valor impossível: NaN, infinito, tipo errado, fora da faixa contratada,
    contagem negativa, ou bool travestido de número."""

    category = "invalid_value"


class DuplicateIndicator(AssemblyError):
    """O mesmo id de indicador apareceu mais de uma vez nos fatos."""

    category = "duplicate_indicator"


class MissingRequiredFact(AssemblyError):
    """Um fato obrigatório do envelope não veio (ex.: `analysis_id`, `analyzed_at`)."""

    category = "missing_required_fact"


class UnsafeEvidence(AssemblyError):
    """A evidência traz campo fora da allowlist pública, ou conteúdo proibido."""

    category = "unsafe_evidence"


class SchemaMismatch(AssemblyError):
    """O payload não tem a forma declarada — inclui campo extra não contratado."""

    category = "schema_mismatch"


class AssemblyInvariantViolation(AssemblyError):
    """Contradição interna que nenhuma das categorias acima descreve com precisão
    (ex.: disponibilidade e valor se contradizem, prioridade ausente, ordem duplicada)."""

    category = "assembly_invariant_violation"


#: Todas as categorias públicas, para documentação e teste de sincronização.
ERROR_CATEGORIES: tuple[str, ...] = (
    UnsupportedFactsVersion.category,
    UnsupportedMeasurementVersion.category,
    UnknownIndicator.category,
    InvalidUnit.category,
    InvalidDenominator.category,
    InvalidValue.category,
    DuplicateIndicator.category,
    MissingRequiredFact.category,
    UnsafeEvidence.category,
    SchemaMismatch.category,
    AssemblyInvariantViolation.category,
)
