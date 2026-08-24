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

import logging
import re

from result_assembler.contracts.facts import MAX_EXCERPT_LEN, AnalysisFacts
from result_assembler.errors import UnsafeEvidence

LOGGER = logging.getLogger(__name__)

#: Limite de tamanho: rótulo é rótulo. Texto longo é conteúdo disfarçado de rótulo.
MAX_LABEL_LEN = 120

#: Teto do texto de ALERTA — maior que o de rótulo, e ainda um teto.
#:
#: `title` e `detail` são frases escritas pelo MOTOR para uma pessoa ler, e legitimamente passam
#: de 120 caracteres. O que o teto impede é o que já aconteceu uma vez: uma frase montada
#: interpolando campo de dado do cliente. Trecho de conversa é longo por natureza, e um teto de
#: tamanho pega isso sem precisar reconhecer o conteúdo — que nenhum regex reconhece.
MAX_ALERT_TEXT_LEN = 400

#: `NO_TRECHO` marca os padroes que valem TAMBEM para o trecho de conversa.
#:
#: A marcacao e ESTRUTURAL, no ponto da definicao, e nao uma lista de nomes em outro lugar. A
#: primeira versao deste conserto casava por nome — e `"identidade de execução"` tem acento, entao
#: a comparacao com a lista falhava e o padrao era PULADO. Falhava ABERTA: `worker_id` atravessava
#: para o documento publico, e nenhum tipo reclamava.
#:
#: Com a marca no proprio tuple, "esquecer de sincronizar" deixa de ser possivel: nao ha segunda
#: lista para desincronizar.
NO_TRECHO = True
SO_NO_ROTULO = False

#: Cada entrada: (nome, padrao, vale_no_trecho).
#:
#: Os `SO_NO_ROTULO` foram escritos para prosa DO MOTOR num campo de 120 caracteres. O trecho e
#: prosa DO CLIENTE, e aplicar a mesma regua a ela recusa conversa banal. Medido, nao suposto —
#: tres respostas de suporte perfeitamente normais derrubavam a analise inteira:
#:
#:   "Voce pode alterar a senha no aplicativo"       -> `credencial`, pela PALAVRA "senha"
#:   "Para redefinir sua senha, acesse https://..."  -> `url`, pelo link de ajuda da empresa
#:   "Please select your plan from the list below"   -> `sql/tabela`, por "select ... from"
#:
#: O Privacy Gate redige VALORES sensiveis; ele nao redige — nem deve — a palavra "senha". Quem
#: fala de senha com o suporte e o cliente, e e justamente a conversa que a evidencia existe para
#: mostrar. O arquetipo da resposta generica reusada entre intencoes cai no primeiro caso.
#:
#: Os `NO_TRECHO` sao o que NUNCA e prosa de suporte legitima e indica vazamento do NOSSO lado.
_PADROES_PROIBIDOS: tuple[tuple[str, re.Pattern[str], bool], ...] = (
    (
        "caminho absoluto",
        re.compile(r"(^|[\s\"'(])(/[a-zA-Z0-9._-]+){2,}|[A-Za-z]:\\"),
        NO_TRECHO,
    ),
    (
        # A URL GENERICA fica fora do trecho: um link de ajuda da empresa e a coisa mais comum
        # numa resposta de suporte, e era ele que derrubava a analise.
        "url",
        re.compile(r"\b[a-z][a-z0-9+.-]*://", re.IGNORECASE),
        SO_NO_ROTULO,
    ),
    (
        # URL COM CREDENCIAL (`scheme://usuario:senha@host`). Esta vale no trecho, e a distincao
        # e a mesma da palavra vs. valor: `https://ajuda.acme.com/conta` e prosa de suporte;
        # `https://user:pass@interno/painel` nunca e.
        #
        # Achado da revisao independente. Ao tirar `url` do trecho eu tirei junto a deteccao de
        # string de conexao, que era o unico padrao que a pegava — um corte largo demais.
        "credencial em url",
        re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@", re.IGNORECASE),
        NO_TRECHO,
    ),
    (
        # DSN DE INFRAESTRUTURA. Nenhum destes esquemas aparece em conversa de cliente, com ou
        # sem credencial embutida: o host sozinho ja e topologia interna.
        "dsn de infraestrutura",
        re.compile(
            r"\b(postgres(ql)?|mysql|mariadb|mongodb(\+srv)?|redis(s)?|amqp(s)?|kafka"
            r"|mssql|oracle|clickhouse|elasticsearch|memcached|ldap(s)?)://",
            re.IGNORECASE,
        ),
        NO_TRECHO,
    ),
    (
        # VARIAVEL DE AMBIENTE SENSIVEL (`DATABASE_URL=...`, `API_TOKEN=...`). O `credencial com
        # valor` cobria `token=`/`senha=` em minusculas; a forma que vaza de verdade e a do
        # ambiente, em CAIXA ALTA com sufixo.
        "variavel de ambiente",
        re.compile(
            r"\b[A-Z][A-Z0-9_]*_(URL|URI|DSN|KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIALS?)"
            r"\s*[:=]"
        ),
        NO_TRECHO,
    ),
    (
        # A PALAVRA. Fica fora do trecho: "Voce pode alterar a senha no aplicativo" e a resposta
        # de suporte mais comum que existe, e era ela que derrubava a analise.
        "credencial",
        re.compile(r"(?i)\b(bearer|token|secret|password|api[_-]?key|senha)\b"),
        SO_NO_ROTULO,
    ),
    (
        # O VALOR. Este vale no trecho, e a distincao e a que importa: o Privacy Gate redige
        # valores sensiveis do CLIENTE, e este padrao pega o que o NOSSO lado colaria — um header
        # de autorizacao, um token de portador, um prefixo de fornecedor, um par chave=valor.
        #
        # Nenhuma das formas abaixo aparece em prosa de suporte: "Seu token de acesso expirou"
        # nao tem `:` nem `=` depois de "token", e "redefinir sua senha," tem virgula.
        "credencial com valor",
        re.compile(
            r"(?i)(\bauthorization\s*:"
            r"|\bbearer\s+[\w\-._~+/]{8,}"
            r"|\b(sk|pk|ghp|gho|xox[abp])[-_][A-Za-z0-9\-_]{6,}"
            r"|\b(api[_-]?key|secret|token|password|senha)\s*[:=]\s*\S)"
        ),
        NO_TRECHO,
    ),
    ("chave privada", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY"), NO_TRECHO),
    (
        "stack trace",
        re.compile(
            r"(?i)(traceback \(most recent call last\)" r"|\bat [\w.$]+\(.*\.(java|py|ts|js):\d+)"
        ),
        NO_TRECHO,
    ),
    ("exceção", re.compile(r"(?i)\b\w*(Error|Exception)\b\s*:"), NO_TRECHO),
    (
        "sql/tabela",
        re.compile(
            r"(?i)\b(select\s+.*\s+from|insert\s+into|update\s+\w+\s+set"
            r"|from\s+orchestrator_\w+)\b"
        ),
        SO_NO_ROTULO,
    ),
    (
        # SQL contra as NOSSAS tabelas, separado do `select ... from` generico que casa com
        # ingles comum. O generico fica fora do trecho; este nao.
        "tabela nossa",
        re.compile(r"(?i)\bfrom\s+orchestrator_\w+\b"),
        NO_TRECHO,
    ),
    (
        "identidade de execução",
        re.compile(
            r"(?i)\b(worker[_-]?id|engine[_-]?version|lease[_-]?token"
            r"|attempt[_-]?id|job[_-]?id|instance[_-]?id)\b"
        ),
        NO_TRECHO,
    ),
    ("chave de objeto", re.compile(r"(?i)\b(s3|minio|bucket|object[_-]?key)\b"), NO_TRECHO),
)



def trecho_publicavel(texto: str | None, onde: str) -> str | None:
    """O trecho, ou `None` quando ele nao pode ser publicado. **Nunca levanta.**

    A diferenca de comportamento em relacao a `_varrer` e deliberada, e e o achado que a revisao
    da Regra #16 pegou: recusar e a resposta certa para `id`, `kind` e `label`, que sao NOSSOS —
    um id com `Bearer sk-live-...` e um defeito nosso e o documento nao deve sair. Para o trecho e
    a resposta errada: o conteudo dele e, por decisao do owner, do CLIENTE. Recusar a montagem
    publica NADA — nem v3, nem v1 — por causa de uma palavra numa conversa de suporte.

    Descartar o trecho e estritamente melhor nas duas pontas: nunca publica o conteudo suspeito
    (mesma garantia da recusa) e nao derruba o resultado (o que a recusa fazia).

    LIMITACAO ESCRITA: o descarte fica no LOG, nao no documento. `PublicEvidenceSummaryV3` nao tem
    campo de motivo, e cria-lo e mais uma versao de contrato com ordem de deploy. Depois do
    estreitamento acima, o descarte so dispara em vazamento NOSSO — que e defeito, nao rotina —,
    e por isso o log e proporcional. Se virar rotina, o campo passa a valer.
    """
    try:
        return _trecho_publicavel(texto, onde)
    except Exception:
        # A promessa "NUNCA levanta" e absoluta, e sem isto ela dependia de o argumento se
        # comportar. Uma subclasse de `str` com `strip` ou `__len__` hostil passava pela guarda
        # de tipo e levantava dentro do `re` — achado da revisao independente.
        #
        # Inalcancavel pelo caminho contratado, e e justamente por isso que a excecao aqui
        # significa "aconteceu algo que ninguem previu": descartar o trecho e a resposta segura,
        # e derrubar o documento seria repetir o defeito que esta funcao existe para consertar.
        LOGGER.warning("trecho descartado em %s: falha inesperada ao avaliar", onde)
        return None


def _trecho_publicavel(texto: str | None, onde: str) -> str | None:
    if texto is None:
        return None
    if not isinstance(texto, str):
        # A promessa "nunca levanta" e forte, e sem esta guarda ela era FALSA: `bytes`, `int` e
        # `list` levantavam `TypeError` dentro do `re`. Inalcancavel pelo caminho contratado
        # (`FactEvidenceSummary.excerpt` e `str | None` e o pydantic valida antes), e a funcao e
        # exportada — quem a chamar de fora nao tem essa garantia.
        #
        # Descartar e a resposta certa tambem aqui: um trecho que nem e texto nao e publicavel, e
        # derrubar o documento por isso repetiria o defeito que esta funcao existe para consertar.
        LOGGER.warning("trecho descartado em %s: tipo inesperado (%s)", onde, type(texto).__name__)
        return None
    if not texto.strip():
        # Vazio nao e trecho. Publicar `""` faz a tela desenhar uma citacao em branco, que afirma
        # "o trecho e este" apontando para nada.
        return None
    if len(texto) > MAX_EXCERPT_LEN:
        LOGGER.warning("trecho descartado em %s: excede %d caracteres", onde, MAX_EXCERPT_LEN)
        return None
    for nome, padrao, vale_no_trecho in _PADROES_PROIBIDOS:
        if vale_no_trecho and padrao.search(texto):
            # Nunca ecoa o texto: ecoar no log copiaria para o log exatamente o que se quer
            # manter fora do documento.
            LOGGER.warning("trecho descartado em %s: conteudo proibido (%s)", onde, nome)
            return None
    return texto


def _varrer(texto: str, onde: str, *, teto: int = MAX_LABEL_LEN) -> None:
    if len(texto) > teto:
        raise UnsafeEvidence(
            f"texto excede {teto} caracteres — rótulo não carrega conteúdo",
            location=onde,
        )
    for nome, padrao, _ in _PADROES_PROIBIDOS:
        if padrao.search(texto):
            # A mensagem diz o TIPO do problema e ONDE. Nunca ecoa o trecho: ecoar aqui
            # copiaria o segredo para o log, que é exatamente o que se quer evitar.
            raise UnsafeEvidence(f"conteúdo proibido detectado ({nome})", location=onde)


def validate_evidence_safety(facts: AnalysisFacts) -> None:
    """Recusa qualquer TEXTO PUBLICADO que carregue conteúdo não publicável.

    Cobre evidência, recomendação, **alerta** e **intenção**. O nome ficou `evidence` por
    herança.

    **O que ela NÃO cobre, escrito em vez de subentendido:** `issues[]` e
    `executive_summary.text` são publicáveis pelo contrato e não têm produtor hoje — varrê-los
    seria gate sobre o vazio. `executive_summary.text` não tem sequer teto de tamanho. No dia em
    que ganharem produtor, entram aqui **antes** de a fiação subir; é a mesma dívida que os
    alertas pagaram: a família passou a ser publicada e a rede não veio junto.

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
        # O TRECHO **nao e varrido aqui**, e a ausencia e o conserto.
        #
        # Ele carrega texto de conversa por decisão do owner, sobre uma premissa que mudou: o
        # Privacy Gate é porta única e o clearance é garantido por constraint. Ver
        # `FactEvidenceSummary`.
        #
        # A protecao continua existindo — em `trecho_publicavel`, chamada na MONTAGEM, que
        # DESCARTA o trecho em vez de recusar o documento. Levantar aqui derrubava a analise
        # inteira por uma palavra numa conversa de suporte, e derrubava tambem o v1, que nem
        # publica o trecho. Ver a docstring de `trecho_publicavel`.
    for i, rec in enumerate(facts.recommendations):
        _varrer(rec.id, f"recommendations[{i}].id")
        # O título da recomendação é texto público exibido ao usuário — mesma régua.
        _varrer(rec.title, f"recommendations[{i}].title")
        if rec.category is not None:
            _varrer(rec.category, f"recommendations[{i}].category")
        for j, ref in enumerate(rec.evidence_refs):
            _varrer(ref, f"recommendations[{i}].evidence_refs[{j}]")
    # OS ALERTAS, e por que eles entraram só agora.
    #
    # Quando esta função nasceu, `alerts` não era publicado — viajava como `[]`, e varrer uma
    # família que ninguém lê seria gate sobre o vazio. Ela passou a ser publicada, e com ela veio
    # um vazamento medido: o `hint` de `GENERIC_CROSS_INTENT_REUSE` interpolava
    # `example_reply`, que é a resposta do assistente do CLIENTE, e virava `alerts[].detail` no
    # documento público.
    #
    # A origem foi corrigida no motor. Isto aqui é a rede: a próxima frase montada com campo de
    # dado do cliente não depende de alguém lembrar da regra.
    #
    # `getattr` e nao `facts.alerts`: esta funcao recebe os TRES envelopes. `AnalysisFacts` (v1)
    # nao tem a familia — ela nasceu no v2 —, e `facts.alerts` levanta `AttributeError` no
    # caminho v1, que continua vivo. O envelope sem a familia nao tem o que varrer, e pular e a
    # resposta certa: a ausencia da familia nao e um alerta vazio, e nenhum texto sai por ela.
    for i, al in enumerate(getattr(facts, "alerts", None) or ()):
        _varrer(al.id, f"alerts[{i}].id")
        _varrer(al.code, f"alerts[{i}].code")
        _varrer(al.title, f"alerts[{i}].title", teto=MAX_ALERT_TEXT_LEN)
        if al.detail is not None:
            _varrer(al.detail, f"alerts[{i}].detail", teto=MAX_ALERT_TEXT_LEN)
        for j, ref in enumerate(al.evidence_refs):
            _varrer(ref, f"alerts[{i}].evidence_refs[{j}]")
        # `affected_intents` e a MESMA string que alimenta o `hint` do motor — e o `hint` vira
        # `detail`, que e varrido. O mesmo texto estava fail-closed num campo e livre no vizinho.
        for j, it in enumerate(al.affected_intents):
            _varrer(it, f"alerts[{i}].affected_intents[{j}]")
    # A FAMILIA `intents`, pelo mesmo motivo.
    #
    # `intent_id` e o nome da intencao vindo do dataset do CLIENTE — texto livre quando o cliente
    # mapeia uma coluna livre. `severity_reason` e frase do motor. Os dois sao publicados e
    # nenhum passava por aqui.
    for i, it in enumerate(getattr(facts, "intents", None) or ()):
        _varrer(it.intent_id, f"intents[{i}].intent_id")
        for j, motivo in enumerate(it.severity_reason or ()):
            _varrer(motivo, f"intents[{i}].severity_reason[{j}]", teto=MAX_ALERT_TEXT_LEN)
