"""Codex R5 [1] — a correção do R2 reintroduziu o vazamento que o R3 fechou.

`parse_facts` colocava o `loc` do pydantic direto na localização do erro. O `loc` inclui a
**chave** do campo extra, e a chave é payload. Um envelope com um campo chamado
`"Bearer sk-live-..."` levaria o token para o log de quem capturasse `AssemblyError`.
"""

from __future__ import annotations

from typing import Any

import pytest

from massas import carregar_json, com_indicador
from result_assembler import SchemaMismatch, parse_facts

SEGREDO = "Bearer sk-live-SEGREDO-NO-NOME-DO-CAMPO"
CAMINHO = "/var/lib/sentinela/jobs/an-1/dataset.jsonl"


@pytest.fixture
def bruto() -> dict[str, Any]:
    return carregar_json("massa_a_principal.facts.json")


@pytest.mark.security
class TestLocalizacaoNaoEcoaOPayload:
    @pytest.mark.parametrize("nome", [SEGREDO, CAMINHO, "senha=hunter2"])
    def test_nome_de_campo_extra_nao_aparece_no_erro(self, bruto, nome):
        with pytest.raises(SchemaMismatch) as exc:
            parse_facts(com_indicador(bruto, **{nome: 1}))
        assert nome not in str(exc.value)

    def test_campo_extra_no_topo_do_envelope(self, bruto):
        with pytest.raises(SchemaMismatch) as exc:
            parse_facts({**bruto, SEGREDO: 1})
        assert SEGREDO not in str(exc.value)

    def test_campo_extra_aninhado_em_evidencia(self):
        f = carregar_json("massa_f_recomendacoes_evidencias.facts.json")
        f["evidence"][0][SEGREDO] = 1
        with pytest.raises(SchemaMismatch) as exc:
            parse_facts(f)
        assert SEGREDO not in str(exc.value)

    def test_localizacao_continua_util_para_depurar(self, bruto):
        """Ocultar o segmento desconhecido não pode custar a capacidade de depurar: o
        caminho contratado até ele precisa sobreviver."""
        with pytest.raises(SchemaMismatch) as exc:
            parse_facts(com_indicador(bruto, **{SEGREDO: 1}))
        texto = str(exc.value)
        assert "indicators" in texto
        assert "<campo-nao-contratado>" in texto

    def test_erro_em_campo_contratado_mostra_o_nome(self, bruto):
        """Contra-prova: nome CONTRATADO não é segredo e continua aparecendo — senão a
        mensagem viraria inútil."""
        with pytest.raises(SchemaMismatch) as exc:
            parse_facts(com_indicador(bruto, value="texto"))
        assert "indicators.0.value" in str(exc.value)


@pytest.mark.security
def test_todo_campo_contratado_e_reconhecido():
    """Se um modelo ganhar campo novo e o conjunto não for atualizado, o nome legítimo
    apareceria como `<campo-nao-contratado>` e a mensagem pioraria em silêncio."""
    from result_assembler import _CAMPOS_CONTRATADOS
    from result_assembler.contracts.facts import AnalysisFacts, FactIndicator

    assert set(AnalysisFacts.model_fields) <= _CAMPOS_CONTRATADOS
    assert set(FactIndicator.model_fields) <= _CAMPOS_CONTRATADOS
