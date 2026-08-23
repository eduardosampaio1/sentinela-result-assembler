"""O TEXTO DO ALERTA não atravessa carregando conversa de cliente.

## O defeito que estes casos fecham

A família `alerts` nasceu não publicada — viajava como `[]` — e a varredura de conteúdo nunca
a cobriu. Quando ela passou a ser publicada, veio junto um caminho medido:

    `_sentinela_cross_intent.py`   "example_reply": convs[...].assistant_text
    `core/alertas.py`             "hint": f"... Example: {example_reply[:160]}"
    `from_engine_result.py`       detail = hint
    `assemble_v3.py`              alerts[].detail  →  documento PÚBLICO

Até 160 caracteres da resposta do assistente do cliente, publicados.

E havia um segundo buraco, anterior: **`assemble_v3` nunca chamou `validate_evidence_safety`**.
O v1 e o v2 chamavam; o caminho de produção, não. A rede existia, tinha teste, e não cobria
nada do que sai.

## O que estes casos provam, e o que NÃO provam

Provam que o texto do alerta é varrido e que o teto de tamanho vale. **Não** provam que uma
frase curta com conteúdo de cliente seria pega — nenhum regex distingue prosa do motor de prosa
do cliente, e afirmar isso aqui seria prometer mais do que o código faz.

A defesa de verdade é a primeira camada, e ela é humana: ninguém monta frase pública
interpolando campo de dado do cliente. O teto é o que pega o caso comum, porque trecho de
conversa é longo por natureza.
"""

from __future__ import annotations

import pytest

from result_assembler import assemble_v3
from result_assembler.contracts.facts import AnalysisFactsV3
from result_assembler.errors import UnsafeEvidence


def _fatos(alerta: dict) -> AnalysisFactsV3:
    return AnalysisFactsV3.model_validate(
        {
            "facts_schema_version": "analysis-facts-v3",
            "measurement_contract_version": "measurement-1.0",
            "identity": {"analysis_id": "an-teste"},
            "window": {"analyzed_at": "2026-08-23T12:00:00+00:00", "record_count": 10},
            "provenance": {"engine_version": "e1"},
            "indicators": [],
            "dimensions": [],
            "recommendations": [],
            "evidence": [],
            "alerts": [alerta],
        }
    )


ALERTA_OK = {
    "id": "cross_intent_reuse-a-b",
    "severity": "high",
    "code": "CROSS_INTENT_REUSE",
    "title": "Cross-intent reuse detected",
    "detail": "Very similar answers across intents (a,b). Consider templates per intent.",
}


def test_o_alerta_do_MOTOR_atravessa() -> None:
    """A frase que o motor escreve para uma pessoa ler continua passando.

    Sem este caso, o gate poderia estar recusando TUDO e os outros dois passariam por motivo
    errado — a família sairia vazia e ninguém veria diferença.
    """
    fora = assemble_v3(_fatos(ALERTA_OK))
    assert len(fora.public_result.alerts) == 1
    assert fora.public_result.alerts[0].detail == ALERTA_OK["detail"]


def test_detalhe_LONGO_e_recusado() -> None:
    """Trecho de conversa é longo por natureza, e o teto é o que o pega.

    400 caracteres é folga para a frase do motor e curto para um trecho colado.
    """
    alerta = {**ALERTA_OK, "detail": "Example: " + ("resposta do assistente ao cliente " * 20)}
    with pytest.raises(UnsafeEvidence) as erro:
        assemble_v3(_fatos(alerta))
    assert "alerts[0].detail" in str(erro.value.location)
    # A mensagem NUNCA ecoa o trecho: ecoar copiaria o conteúdo para o log, que é exatamente
    # o que se quer evitar. Ela diz o tipo e o lugar.
    assert "resposta do assistente" not in str(erro.value)


def test_titulo_com_credencial_e_recusado() -> None:
    """O `title` é varrido pelos mesmos padrões, e não só o `detail`."""
    with pytest.raises(UnsafeEvidence):
        assemble_v3(_fatos({**ALERTA_OK, "title": "Bearer sk-live-vazou"}))


def test_o_caminho_v3_CHAMA_a_varredura() -> None:
    """O cadeado do cadeado.

    Os três casos acima passariam iguais se `assemble_v3` deixasse de chamar
    `validate_evidence_safety` — nenhum deles olha a chamada, só o efeito. Se o efeito sumisse,
    eles falhariam; mas eles falhariam DEPOIS, e a pergunta "por quê" custaria uma investigação.
    Este caso responde direto.
    """
    import inspect

    from result_assembler.assembler import assemble_v3 as modulo

    fonte = inspect.getsource(modulo.assemble_v3)
    assert "validate_evidence_safety(facts)" in fonte
