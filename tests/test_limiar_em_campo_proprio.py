"""O limiar atravessa em campo PRÓPRIO, e nunca no da escala.

Contexto, porque o desenho errado passou primeiro e nenhum teste o pegou: a primeira versão
desta fatia gravava os dois cortes do motor (`THR_WARN=75`, `THR_CRIT=60`) em
`Scale.minimum/maximum`. A revisão adversarial derrubou. O motivo não é validação — a
validação de faixa lê `_FAIXAS_CANONICAS[scale.kind]` e ignora `minimum/maximum`, então
`minimum=60` NÃO recusaria um valor de 30. O motivo é pior, porque é silencioso: o consumidor
renderiza aqueles dois campos como a RÉGUA (`medicaoV3.escalaEscrita`, três chamadores), então
`behavior_score` apareceria na tela dizendo `60–75` sendo um número que vive em 0..100. Duas
verdades para um fato, na tela, com a suíte verde.

O gate que importa desta fatia é o `TestNaoVoltaParaAEscala`: ele reprova a volta do desenho
derrubado. Os outros protegem a travessia e a ausência.

Não há teste de "orientação": não há campo de orientação. A ORDEM dos cortes carrega a
direção (`critical < warn` = menor é pior), e um campo afirmando o que a ordem já diz seria
segunda cópia do mesmo fato — com um validador para reconciliá-las, que é o arranjo que a
Regra 14 existe para impedir. O que sobra a testar é que a ordem SOBREVIVE à travessia, e é o
que `test_a_ordem_dos_cortes_sobrevive` faz: uma troca de `warn` por `critical` no transporte
inverteria as zonas na tela sem mudar nenhum número.
"""

from __future__ import annotations

import copy
import json
import pathlib

import pytest
from pydantic import ValidationError

from result_assembler import assemble_v3, parse_facts
from result_assembler.assembler.assemble_v3 import _publicar_limiar
from result_assembler.contracts.facts import (
    Availability,
    FactIndicator,
    FactScore,
    FactThresholds,
    Reason,
)
from result_assembler.contracts.result_v3 import (
    PublicMeasurement,
    PublicThresholds,
    Scale,
    ScaleKind,
)
from result_assembler.version import FACTS_SCHEMA_V3_VERSION

FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "fixtures"

#: O par real do motor: `core/_sentinela_config.py:35`. `critical < warn` = menor é pior.
WARN, CRIT = 75.0, 60.0

_PROC = {"calculation_version": "1.0", "source": "core._engine_helpers"}
_LIMIAR = {"warn": WARN, "critical": CRIT}


def _documento(*, limiar_no_escore=_LIMIAR, limiar_na_intencao=_LIMIAR, valor=77.4) -> dict:
    """Documento v3 com `behavior_score` e uma intenção. `None` omite o limiar."""
    doc = json.loads(
        (FIXTURES / "massa_d1_todas_as_saidas.facts.json").read_text(encoding="utf-8")
    )
    doc = copy.deepcopy(doc)
    doc["facts_schema_version"] = FACTS_SCHEMA_V3_VERSION

    escore = {"id": "behavior_score", "value": valor, "availability": "available",
              "reason": "ok", **_PROC}
    if limiar_no_escore is not None:
        escore["thresholds"] = dict(limiar_no_escore)
    # Um segundo escore SEM limiar, que é o caso das outras 36 saídas do catálogo.
    outro = {"id": "global_confidence", "value": 0.83, "availability": "available",
             "reason": "ok", **_PROC}
    doc["scores"] = [escore, outro]

    intencao_escore = {"id": "intent_score", "value": 82.0, "availability": "available",
                       "reason": "ok", **_PROC}
    if limiar_na_intencao is not None:
        intencao_escore["thresholds"] = dict(limiar_na_intencao)
    doc["intents"] = [{"intent_id": "saudacao", "support": 12, "score": intencao_escore}]
    doc["method"] = {"min_samples_per_intent": 5}
    return doc


def _publicado(doc: dict) -> dict:
    return assemble_v3(parse_facts(doc)).public_result.model_dump(mode="json")


def _medida(pub: dict, id_publico: str) -> dict:
    return next(s["measurement"] for s in pub["scores"] if s["measurement"]["id"] == id_publico)


# ═══════════════════════════════════════════════════════════════════════════════════════
# O gate da fatia: o limiar não volta para o campo da escala
# ═══════════════════════════════════════════════════════════════════════════════════════


class TestNaoVoltaParaAEscala:
    """Se alguém reintroduzir os cortes em `Scale`, é AQUI que reprova.

    Sem este gate a regressão é invisível: a suíte fica verde, o documento fica válido, e a
    tela passa a escrever `60–75` no lugar onde ela diz em que régua o número vive.
    """

    def test_a_escala_do_escore_com_limiar_nao_ganha_minimo_nem_maximo(self):
        m = _medida(_publicado(_documento()), "behavior_score")
        assert m["thresholds"] == {"warn": WARN, "critical": CRIT}
        assert m["scale"]["kind"] == "score_100"
        assert m["scale"]["minimum"] is None, "limiar vazou para o campo da régua"
        assert m["scale"]["maximum"] is None, "limiar vazou para o campo da régua"

    def test_a_escala_da_intencao_com_limiar_tampouco(self):
        pub = _publicado(_documento())
        escore = pub["intents"][0]["score"]
        assert escore["thresholds"] == {"warn": WARN, "critical": CRIT}
        assert escore["scale"]["minimum"] is None
        assert escore["scale"]["maximum"] is None

    def test_limiar_e_escala_sao_campos_diferentes_no_schema_publicado(self):
        """O contrato publicado precisa dizer isso, não só o modelo em memória."""
        raiz = pathlib.Path(__file__).resolve().parent.parent
        schema = json.loads(
            (raiz / "schemas" / "analysis-result-v3.schema.json").read_text(encoding="utf-8")
        )
        defs = schema["$defs"]
        assert sorted(defs["PublicThresholds"]["properties"]) == ["critical", "warn"]
        assert sorted(defs["Scale"]["properties"]) == ["kind", "maximum", "minimum"]
        medida = defs["PublicMeasurement"]["properties"]
        assert "thresholds" in medida and "scale" in medida


# ═══════════════════════════════════════════════════════════════════════════════════════
# A travessia
# ═══════════════════════════════════════════════════════════════════════════════════════


class TestTravessia:
    def test_a_ordem_dos_cortes_sobrevive(self):
        """Uma troca de `warn` por `critical` no transporte inverteria as zonas na tela.

        Nenhum número mudaria, nenhum invariante falharia — os dois cortes continuariam
        finitos e distintos. Só a leitura mudaria de "abaixo de 60 é crítico" para "acima de
        75 é crítico". Por isso o teste afirma os valores por NOME, não a distinção.
        """
        m = _medida(_publicado(_documento()), "behavior_score")
        assert m["thresholds"]["warn"] == WARN
        assert m["thresholds"]["critical"] == CRIT
        assert m["thresholds"]["critical"] < m["thresholds"]["warn"], "menor é pior"

    # Uma por ZONA. A primeira versão deste teste usava só `77.4` — acima de `warn` — e a
    # mutação que "ajustava" o valor para dentro da zona (`max(value, critical)`) SOBREVIVEU:
    # com 77.4 contra critical 60, o clamp é no-op. O teste estava verde porque o dado não
    # exercitava a mutação, não porque o código estivesse correto.
    @pytest.mark.parametrize(
        "valor,zona",
        [(42.0, "abaixo do crítico"), (67.0, "entre os cortes"), (88.0, "acima do warn")],
    )
    def test_o_limiar_nao_altera_o_valor(self, valor, zona):
        com = _medida(_publicado(_documento(valor=valor)), "behavior_score")["value"]
        sem = _medida(
            _publicado(_documento(limiar_no_escore=None, valor=valor)), "behavior_score"
        )["value"]
        assert com == sem == valor, f"o limiar mexeu no valor {zona}"

    def test_maior_e_pior_tambem_atravessa(self):
        """A ordem invertida é forma legítima — custo, risco, drift. O contrato não a proíbe."""
        doc = _documento(limiar_no_escore={"warn": 0.5, "critical": 0.8})
        doc["scores"][0] = {"id": "semantic_drift", "value": 0.31,
                            "availability": "available", "reason": "ok",
                            "thresholds": {"warn": 0.5, "critical": 0.8}, **_PROC}
        m = _medida(_publicado(doc), "semantic_drift")
        assert m["thresholds"] == {"warn": 0.5, "critical": 0.8}
        assert m["thresholds"]["critical"] > m["thresholds"]["warn"], "maior é pior"


# ═══════════════════════════════════════════════════════════════════════════════════════
# A ausência — o caso das outras 36
# ═══════════════════════════════════════════════════════════════════════════════════════


class TestAusencia:
    def test_metrica_sem_limiar_sai_com_null_nunca_com_zero(self):
        """`warn=0` nesta régua é a fronteira mais severa possível.

        Absence-as-zero aqui não some da tela: aparece como alarme.
        """
        m = _medida(_publicado(_documento()), "global_confidence")
        assert m["thresholds"] is None

    def test_documento_inteiro_sem_limiar_nenhum(self):
        pub = _publicado(_documento(limiar_no_escore=None, limiar_na_intencao=None))
        assert all(s["measurement"]["thresholds"] is None for s in pub["scores"])
        assert pub["intents"][0]["score"]["thresholds"] is None

    def test_a_ausencia_atravessa_como_ausencia_na_conversao(self):
        assert _publicar_limiar(None) is None

    def test_limiar_sobre_medicao_ausente_e_permitido(self):
        """O vão com zonas: a tela sabe onde ficaria o bom, e não desenha traço sem régua.

        O limiar é propriedade da MÉTRICA, não desta medição — então ele não depende de ter
        dado. Proibi-lo faria a ausência perder justamente a referência que a explica.
        """
        m = PublicMeasurement(
            id="behavior_score", value=None, availability=Availability.UNAVAILABLE,
            reason=Reason.NO_INPUT_DATA, scale=Scale(kind=ScaleKind.SCORE_100),
            thresholds=PublicThresholds(warn=WARN, critical=CRIT),
        )
        assert m.value is None and m.thresholds.warn == WARN


# ═══════════════════════════════════════════════════════════════════════════════════════
# Os invariantes, nas DUAS fronteiras
# ═══════════════════════════════════════════════════════════════════════════════════════


class TestInvariantesDoFato:
    """Fronteira de ENTRADA: produtor externo manda par inválido → recusa na porta."""

    @pytest.mark.parametrize("warn,critical", [(75.0, 75.0), (0.0, 0.0), (-1.0, -1.0)])
    def test_cortes_iguais_sao_recusados(self, warn, critical):
        with pytest.raises(ValueError, match="limiares iguais"):
            FactThresholds(warn=warn, critical=critical)

    @pytest.mark.parametrize("valor", [float("inf"), float("-inf"), float("nan")])
    def test_corte_nao_finito_e_recusado(self, valor):
        with pytest.raises(ValidationError, match="finito"):
            FactThresholds(warn=valor, critical=CRIT)

    def test_meio_par_nao_e_representavel(self):
        with pytest.raises(ValidationError):
            FactThresholds(warn=WARN)

    def test_texto_nao_e_coagido_a_numero(self):
        with pytest.raises(ValidationError, match="número"):
            FactThresholds(warn="75", critical=CRIT)

    def test_o_documento_com_par_invalido_e_recusado_na_porta(self):
        """Não basta o modelo recusar: `parse_facts` é a porta real do produtor."""
        from result_assembler.errors import SchemaMismatch

        doc = _documento(limiar_no_escore={"warn": WARN, "critical": WARN})
        with pytest.raises(SchemaMismatch):
            parse_facts(doc)

    def test_o_indicador_do_v1_nao_ganhou_o_campo(self):
        """O `analysis-facts-v1` tem schema publicado congelado byte a byte."""
        assert "thresholds" not in FactIndicator.model_fields
        assert "thresholds" in FactScore.model_fields


class TestInvariantesDoPublico:
    """Fronteira de SAÍDA: montagem produz documento impossível → recusa antes do consumidor.

    Não é o mesmo cadeado do fato. Um par inválido que passasse só a primeira fronteira seria
    fato aceito e documento impossível, e o erro apareceria a dois hops da causa.
    """

    def test_cortes_iguais_sao_recusados(self):
        with pytest.raises(ValueError, match="limiares iguais"):
            PublicThresholds(warn=WARN, critical=WARN)

    @pytest.mark.parametrize("valor", [float("inf"), float("nan")])
    def test_corte_nao_finito_e_recusado(self, valor):
        with pytest.raises(ValidationError, match="finito"):
            PublicThresholds(warn=valor, critical=CRIT)

    def test_corte_fora_da_regua_e_recusado(self):
        """`warn=75` num `ratio_unit` deixa a zona de atenção INALCANÇÁVEL.

        Nenhum valor possível cairia nela, e a tela desenharia uma fronteira fora do eixo.
        """
        with pytest.raises(ValidationError, match="fora da régua"):
            PublicMeasurement(
                id="containment_risk", value=0.2, availability=Availability.AVAILABLE,
                reason=Reason.OK, scale=Scale(kind=ScaleKind.RATIO_UNIT),
                thresholds=PublicThresholds(warn=WARN, critical=CRIT),
            )

    def test_corte_fora_da_regua_e_recusado_mesmo_sem_valor(self):
        """Limiar impossível é erro de montagem HOJE, não quando a 1ª medição aparecer."""
        with pytest.raises(ValidationError, match="fora da régua"):
            PublicMeasurement(
                id="containment_risk", value=None, availability=Availability.UNAVAILABLE,
                reason=Reason.NO_INPUT_DATA, scale=Scale(kind=ScaleKind.RATIO_UNIT),
                thresholds=PublicThresholds(warn=WARN, critical=CRIT),
            )

    def test_escala_sem_faixa_canonica_nao_restringe_o_corte(self):
        """`currency` tem faixa ABERTA — um limiar de custo em dólar não tem teto para violar.

        O invariante só morde onde há régua declarada. Afirmar isto impede a "correção" que
        aplicaria a faixa de `ratio_unit` a tudo.
        """
        m = PublicMeasurement(
            id="projected_token_cost", value=1200.0, availability=Availability.AVAILABLE,
            reason=Reason.OK, scale=Scale(kind=ScaleKind.CURRENCY), unit="USD",
            thresholds=PublicThresholds(warn=1000.0, critical=5000.0),
        )
        assert m.thresholds.critical == 5000.0


# ═══════════════════════════════════════════════════════════════════════════════════════
# A spec é DERIVADA do modelo, e o gate é o que impede a próxima deriva
# ═══════════════════════════════════════════════════════════════════════════════════════


class TestSpecEDerivadaDoModelo:
    """O bloco de campos da §3 lista exatamente os campos que os modelos têm.

    Sem este gate a spec derivou TRÊS vezes, e a última custou caro: o invariante 5 dizia
    "`value` fora de `[scale.min, scale.max]` é erro de montagem", o que fez esta fatia nascer
    gravando os cortes `75/60` em `minimum`/`maximum` supondo restrição onde não havia. A
    validação lê a faixa canônica do `kind`; `minimum`/`maximum` são declarativos e o
    consumidor os renderiza como a régua.

    As outras duas derivas: um `evidence_level` que não existe em modelo nenhum, e o
    `confidence` que a D5 introduziu e ninguém documentou.

    O gate compara NOMES, não prosa. Documento e modelo divergindo em nome é o que faz um
    consumidor implementar contra um campo inexistente.
    """

    ESPECIFICACAO = (
        pathlib.Path(__file__).resolve().parent.parent / "docs" / "ANALYSIS-RESULT-V3-SPEC.md"
    )

    def _campos_citados(self, cabecalho: str) -> set[str]:
        import re

        texto = self.ESPECIFICACAO.read_text(encoding="utf-8")
        # Âncora em INÍCIO DE LINHA. A primeira versão usava `texto.index(cabecalho)` e o
        # alvo `Scale` casou com o FIM da linha `  scale           Scale`, dentro do bloco do
        # `PublicMeasurement` — o teste então comparava os campos da medição com os da escala
        # e reprovava por defeito do instrumento, não do documento.
        casamento = re.search(rf"^{re.escape(cabecalho)}$", texto, re.M)
        assert casamento is not None, f"a spec não declara um bloco `{cabecalho}`"
        # O bloco de um modelo termina na primeira linha em branco depois dele.
        corpo = texto[casamento.end() :].lstrip("\n")
        corpo = corpo[: corpo.index("\n\n")]
        return set(re.findall(r"^  (\w+)", corpo, re.M))

    @pytest.mark.parametrize(
        "cabecalho,modelo",
        [
            ("PublicMeasurement", PublicMeasurement),
            ("Scale", Scale),
            ("PublicThresholds", PublicThresholds),
        ],
    )
    def test_o_bloco_da_spec_lista_os_campos_do_modelo(self, cabecalho, modelo):
        citados = self._campos_citados(cabecalho)
        reais = set(modelo.model_fields)
        assert citados == reais, (
            f"§3 e `{cabecalho}` divergem — "
            f"no modelo e não na spec: {sorted(reais - citados)}; "
            f"na spec e não no modelo: {sorted(citados - reais)}"
        )

    def test_a_spec_nao_afirma_que_minimo_e_maximo_validam(self):
        """A frase que custou o desenho errado não pode voltar."""
        texto = self.ESPECIFICACAO.read_text(encoding="utf-8")
        assert "fora de `[scale.min, scale.max]` é erro de montagem" not in texto
        assert "faixa canônica do `scale.kind`" in texto
