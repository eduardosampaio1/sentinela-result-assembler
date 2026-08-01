"""Segurança do que sai — allowlist, não denylist.

Duas camadas, de propósito:

1. **Allowlist estrutural** (a que vale): `FactEvidenceSummary` só tem quatro campos, e
   `PublicEvidenceSummary` também. Um campo novo no domínio não chega ao público por
   omissão — alguém precisa escrevê-lo aqui. É esta camada que garante a segurança.

2. **Varredura de conteúdo** (rede de proteção): mesmo dentro de um campo permitido, um
   `label` pode carregar um caminho, uma URL, um token ou um trecho de stack trace,
   porque quem preencheu não pensou nisso. A varredura recusa explicitamente em vez de
   deixar passar.

A segunda camada NÃO é a defesa principal — denylist por padrão sempre perde para
criatividade. Ela existe porque `label` é texto vindo de outro sistema, e texto de outro
sistema é onde vazamento acontece.
"""

from __future__ import annotations

import re

from result_assembler.contracts.facts import AnalysisFacts
from result_assembler.errors import UnsafeEvidence

#: Limite de tamanho: rótulo é rótulo. Texto longo é conteúdo disfarçado de rótulo.
MAX_LABEL_LEN = 120

_PADROES_PROIBIDOS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("caminho absoluto", re.compile(r"(^|[\s\"'(])(/[a-zA-Z0-9._-]+){2,}|[A-Za-z]:\\")),
    ("url", re.compile(r"\b[a-z][a-z0-9+.-]*://", re.IGNORECASE)),
    ("credencial", re.compile(r"(?i)\b(bearer|token|secret|password|api[_-]?key|senha)\b")),
    ("chave privada", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY")),
    (
        "stack trace",
        re.compile(
            r"(?i)(traceback \(most recent call last\)" r"|\bat [\w.$]+\(.*\.(java|py|ts|js):\d+)"
        ),
    ),
    ("exceção", re.compile(r"(?i)\b\w*(Error|Exception)\b\s*:")),
    (
        "sql/tabela",
        re.compile(
            r"(?i)\b(select\s+.*\s+from|insert\s+into|update\s+\w+\s+set"
            r"|from\s+orchestrator_\w+)\b"
        ),
    ),
    (
        "identidade de execução",
        re.compile(
            r"(?i)\b(worker[_-]?id|engine[_-]?version|lease[_-]?token"
            r"|attempt[_-]?id|job[_-]?id|instance[_-]?id)\b"
        ),
    ),
    ("chave de objeto", re.compile(r"(?i)\b(s3|minio|bucket|object[_-]?key)\b")),
)


def _varrer(texto: str, onde: str) -> None:
    if len(texto) > MAX_LABEL_LEN:
        raise UnsafeEvidence(
            f"texto excede {MAX_LABEL_LEN} caracteres — rótulo não carrega conteúdo",
            location=onde,
        )
    for nome, padrao in _PADROES_PROIBIDOS:
        if padrao.search(texto):
            # A mensagem diz o TIPO do problema e ONDE. Nunca ecoa o trecho: ecoar aqui
            # copiaria o segredo para o log, que é exatamente o que se quer evitar.
            raise UnsafeEvidence(f"conteúdo proibido detectado ({nome})", location=onde)


def validate_evidence_safety(facts: AnalysisFacts) -> None:
    """Recusa qualquer TEXTO PUBLICADO que carregue conteúdo não publicável.

    Inclui os **ids** (Codex R3 [1]): `evidence.id`, `recommendation.id` e
    `evidence_refs` atravessam para o resultado público tal como chegaram. Um id é
    string livre vinda de outro sistema — chamar de "id" não o torna seguro, e
    `{"id": "Bearer sk-live-..."}` seria publicado sem que nada olhasse.
    """
    for i, ev in enumerate(facts.evidence):
        _varrer(ev.id, f"evidence[{i}].id")
        _varrer(ev.kind, f"evidence[{i}].kind")
        if ev.label is not None:
            _varrer(ev.label, f"evidence[{i}].label")
    for i, rec in enumerate(facts.recommendations):
        _varrer(rec.id, f"recommendations[{i}].id")
        # O título da recomendação é texto público exibido ao usuário — mesma régua.
        _varrer(rec.title, f"recommendations[{i}].title")
        if rec.category is not None:
            _varrer(rec.category, f"recommendations[{i}].category")
        for j, ref in enumerate(rec.evidence_refs):
            _varrer(ref, f"recommendations[{i}].evidence_refs[{j}]")
