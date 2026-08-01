"""Manifesto interno da montagem.

Separado do resultado público de propósito: é o registro técnico de COMO a montagem
aconteceu — o que entrou, o que ficou de fora e por quê. Serve a operação e auditoria,
não ao consumidor final.

Regra: o manifesto explica **decisões**, não **conteúdo**. Ele registra quais indicadores
foram aceitos e quais campos ficaram retidos; não registra valores medidos, textos de
recomendação nem evidências.

**Ele NÃO é publicável** (Codex R3 [2]). Carregar `job_id`, `engine_version` e
`dataset_fingerprint` é o PROPÓSITO dele — sem esses ids não há proveniência técnica.
Esses identificadores podem embutir nome de tenant, de worker ou de ambiente. Portanto:

- seguro no sentido de **não carregar conteúdo analítico**;
- **dado interno** para todo o resto — quem enviar a telemetria trata com a mesma
  classificação de um log de infraestrutura, não como documento de cliente.

A promessa anterior ("pode ir para log/telemetria") era mais forte que o código.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ManifestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class VersionsSeen(ManifestModel):
    """As versões que participaram desta montagem, todas explícitas."""

    assembler_version: str
    facts_schema_version: str
    result_schema_version: str
    measurement_contract_version: str
    indicator_registry_version: str


class InternalManifest(ManifestModel):
    """Proveniência técnica e decisões de montagem."""

    analysis_id: str
    versions: VersionsSeen

    #: Ids internos que o público não carrega — ficam AQUI e só aqui.
    job_id: str | None
    analysis_run_id: str | None
    engine_version: str
    analysis_version: str | None
    dataset_fingerprint: str | None

    #: Ids públicos aceitos, na ordem canônica em que foram publicados.
    accepted_indicator_ids: tuple[str, ...]

    #: Campos que os fatos trouxeram e que a fronteira NÃO deixou atravessar. Não existe
    #: "indicador rejeitado" aqui: sob fail-closed, indicador irregular recusa a montagem
    #: inteira. O que é rejeitado, campo a campo, é o que pertence ao mundo interno —
    #: e listar isso torna a fronteira auditável em vez de implícita.
    withheld_internal_fields: tuple[str, ...]

    #: Observações não fatais (ex.: seção vazia, cobertura declarada).
    warnings: tuple[str, ...]

    #: SHA-256 da serialização canônica do resultado público.
    result_checksum: str
    #: Nome do algoritmo, para que o verificador não precise adivinhar.
    checksum_algorithm: str
