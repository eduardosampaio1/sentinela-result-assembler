# Segurança

O que este pacote protege: **o resultado público não pode carregar nada interno**. Ele é persistido no Result Store, servido pelo Gateway e renderizado no navegador do cliente — três lugares onde qualquer campo interno vira exposição permanente.

## As três camadas

### 1. Allowlist estrutural — a defesa real

Os modelos públicos declaram **exatamente** os campos que existem, e são `extra="forbid"`. Um campo novo no domínio **não chega ao público por omissão**: alguém precisa escrevê-lo em `contracts/result.py`.

O JSON Schema publicado carrega `additionalProperties: false` em todos os objetos — há teste que reprova se um `$defs` perder isso.

### 2. Retenção declarada

O que os fatos trazem e **não** atravessa está listado em `WITHHELD_INTERNAL_FIELDS` e publicado no manifesto:

```
identity.analysis_run_id · identity.job_id
indicators[].calculation_version · indicators[].expected_units
indicators[].observed_units · indicators[].reason · indicators[].source
provenance.analysis_version · provenance.dataset_fingerprint · provenance.engine_version
```

Listar torna a fronteira **auditável** em vez de implícita.

### 3. Varredura de conteúdo — rede de proteção

Mesmo dentro de um campo permitido, `label`, `kind`, `title` e `category` são texto vindo de outro sistema. A varredura recusa: caminho absoluto, URL, credencial (`bearer`/`token`/`secret`/`password`/`api_key`), chave privada, stack trace, exceção, SQL/nome de tabela, identidade de execução (`worker_id`, `lease_token`, `attempt_id`, `job_id`, `engine_version`), chave de objeto (`s3`, `minio`, `bucket`, `object_key`), e texto acima de 120 caracteres.

**Esta camada é denylist e não é a defesa principal** — denylist sempre perde para criatividade. Ela existe porque texto de outro sistema é onde vazamento acontece na prática, e recusar é melhor que deixar passar.

## Erros não vazam

| Regra | Prova |
|---|---|
| mensagem nunca ecoa o payload bruto | `parse_facts` resume o `ValidationError` para caminhos de campo |
| mensagem nunca ecoa o conteúdo proibido detectado | ecoar copiaria o segredo para o log — teste com token real |
| mensagem nunca ecoa o valor medido | teste com `1.4142135`, que aparece só como `indicators[0].value` |

A mensagem carrega **localização segura** (`evidence[0].label`), que basta para depurar.

## O manifesto também é superfície

O manifesto vai para log e telemetria. Ele registra **decisões** (ids aceitos, campos retidos, avisos, checksum, versões) e **não** conteúdo — sem valores medidos, sem textos de recomendação, sem evidências. Há teste que varre o manifesto atrás de valor medido.

## O que ainda não é problema deste pacote

- **Autorização e multi-tenant**: o assembler recebe fatos de UMA análise e devolve o documento dela. Quem pode ler o quê é do Gateway.
- **Criptografia em repouso/trânsito**: pertence a Result Store e Gateway.
- **Rate limiting / DoS**: não há superfície de rede.

## Como verificar

```bash
PYTHONPATH=src python -m pytest tests/ -m security -q
```

E a prova estrutural que independe de massa: `test_nenhum_modelo_publico_declara_campo_interno`.
