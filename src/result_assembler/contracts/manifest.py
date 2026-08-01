"""Manifesto interno da montagem.

Separado do resultado público de propósito: é o registro técnico de COMO a montagem
aconteceu — o que entrou, o que ficou de fora e por quê. Serve a operação e auditoria,
não ao consumidor final.

Regra: o manifesto explica **decisões**, não **conteúdo**. Ele registra que o indicador
`x` foi aceito e que `y` foi excluído por não ter mapeamento público; não registra os
valores, os textos das recomendações nem as evidências. Assim o manifesto pode ir para
log/telemetria sem virar o vazamento que o resultado público evita.
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
