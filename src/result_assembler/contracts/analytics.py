"""O SEGUNDO insumo da montagem: a projeção pública já resolvida (MF6.2).

O Assembler é biblioteca **pura**. Ele não acessa storage, não chama Engine nem Analytics, não
resolve URL assinada, não persiste staging, não recalcula disclosure e **não transforma `withheld`
em erro**. Quem resolve a referência e entrega o documento é a camada de composição do
Orchestrator; aqui ele já chega pronto.

Este módulo descreve o que "pronto" significa: um envelope tipado com o desfecho declarado, as
versões que o identificam, e o conteúdo — que pode legitimamente ser `None`.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ComponentStatus(str, Enum):
    """O que a projeção CONCLUIU. Vocabulário do Analytics, não do Assembler.

    `str, Enum` e não `StrEnum` pela mesma razão do resto da plataforma: o piso é Python 3.10.
    """

    READY = "ready"
    PARTIAL = "partial"
    #: A análise terminou e **nada pôde ser liberado** — o piso de privacidade da MF5. É
    #: conclusão, não ausência: o documento integrado nasce, e nasce com `data: null`.
    WITHHELD = "withheld"


class AnalyticsComponent(BaseModel):
    """A projeção pública resolvida, ou a declaração de que não há o que integrar.

    ## `data` anulável, e por que ele NÃO pode ser obrigatório

    Se o conteúdo fosse exigido, `withheld` viraria falha de montagem — e a MF5 congelou o oposto:
    disclosure é decisão, não defeito. O documento integrado tem de nascer mesmo quando nada foi
    liberado, dizendo isso em vez de morrer.

    ## E por que ele não pode ser opcional NO OUTRO SENTIDO

    `ready`/`partial` **exigem** conteúdo. Um bloco que declarasse `ready` e viesse vazio
    publicaria "há resultado analítico" sobre nada — a mentira mais cara desta plataforma, porque
    parece confiável. O validador abaixo fecha os dois lados.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    component_status: ComponentStatus
    #: Identidade do CONTEÚDO. A composição já o conferiu contra os metadados duráveis antes de
    #: chegar aqui; ele é publicado para que o consumidor possa fazer a mesma conferência.
    projection_digest: str = Field(min_length=1)
    #: Versão do contrato do snapshot. **Distinta** da `measurement_contract_version` da Engine:
    #: reusar uma para as duas faria uma versão descrever duas coisas que evoluem separadas.
    snapshot_contract_version: str = Field(min_length=1)
    #: O documento da projeção, ou `None` quando `withheld`. O Assembler **não o interpreta** —
    #: ele o transporta. Interpretar aqui seria recalcular disclosure fora de quem a decide.
    data: dict[str, Any] | None = None
    #: O denominador analítico (a contagem C da MF6.3), quando há projeção. Vem SEPARADO de
    #: `data` de propósito: é a única coisa que o Assembler precisa LER do lado analítico, e
    #: extraí-la de dentro do documento faria o Assembler conhecer a forma da projeção — que é
    #: exatamente o acoplamento que mantê-lo puro existe para evitar.
    record_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _conteudo_coerente_com_o_desfecho(self) -> AnalyticsComponent:
        if self.component_status is ComponentStatus.WITHHELD:
            if self.data is not None:
                raise ValueError(
                    "withheld com conteúdo: se há algo a liberar, o desfecho não é withheld"
                )
            return self
        if self.data is None:
            raise ValueError(
                f"{self.component_status.value} sem conteúdo: publicar 'há resultado analítico' "
                "sobre nada é pior que não publicar"
            )
        return self


__all__ = ["AnalyticsComponent", "ComponentStatus"]
