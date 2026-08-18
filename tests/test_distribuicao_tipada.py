"""O pacote DISTRIBUÍDO leva os próprios tipos (PEP 561).

Por que isto merece teste: o repositório roda `mypy --strict`, então internamente tudo é
tipado. Mas tipo que não viaja no wheel não existe para quem consome — sem o marcador
`py.typed`, o Orchestrator importa `parse_facts`/`assemble` como `Any` e a fronteira
`analysis-facts-v1` → `analysis-result-v1`, que é justamente onde um erro de tipo custa
caro, deixa de ser checada. O defeito é silencioso: instala, importa e roda.

O teste olha o ARTEFATO construído, não a árvore de fontes — é o artefato que é instalado.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
import unittest
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
FONTE = RAIZ / "src" / "result_assembler" / "py.typed"


class MarcadorNaArvoreTests(unittest.TestCase):
    def test_py_typed_existe_na_fonte(self) -> None:
        self.assertTrue(FONTE.is_file(), "src/result_assembler/py.typed não existe")

    def test_py_typed_esta_vazio(self) -> None:
        """PEP 561: o conteúdo é irrelevante, mas um arquivo com lixo confunde quem lê."""
        self.assertEqual(FONTE.read_bytes(), b"")


class MarcadorNoArtefatoTests(unittest.TestCase):
    """Constrói de verdade e confere o que saiu.

    Construir custa alguns segundos; é o preço de provar a distribuição em vez de
    supor que a configuração de packaging faz o que promete.
    """

    saida: Path
    disponivel: bool

    @classmethod
    def setUpClass(cls) -> None:
        cls.disponivel = False
        try:
            import build  # noqa: F401
        except ImportError:
            return
        cls.saida = RAIZ / "dist" / "_gate_py_typed"
        # LIMPA antes de construir, e nao e higiene: sem isto o gate quebra em todo BUMP DE
        # VERSAO. `build` escreve o artefato com a versao no nome e nao remove os antigos,
        # entao apos 0.2.0 -> 0.3.0 o diretorio guarda os dois e as assercoes de "exatamente
        # um wheel" reprovam — acusando o release em vez do defeito.
        #
        # Medido: foi exatamente o que aconteceu ao subir para 0.3.0.
        if cls.saida.exists():
            shutil.rmtree(cls.saida)
        resultado = subprocess.run(
            [sys.executable, "-m", "build", "--outdir", str(cls.saida), str(RAIZ)],
            capture_output=True,
            text=True,
        )
        if resultado.returncode != 0:  # pragma: no cover - falha de ambiente
            raise AssertionError(f"build falhou:\n{resultado.stdout}\n{resultado.stderr}")
        cls.disponivel = True

    def _pular_sem_build(self) -> None:
        if not self.disponivel:
            self.skipTest("`build` não instalado — gate de distribuição não pôde rodar")

    def test_wheel_contem_py_typed(self) -> None:
        self._pular_sem_build()
        wheels = sorted(self.saida.glob("*.whl"))
        self.assertEqual(len(wheels), 1, f"esperava 1 wheel, achei {wheels}")
        nomes = zipfile.ZipFile(wheels[0]).namelist()
        self.assertIn("result_assembler/py.typed", nomes)

    def test_sdist_contem_py_typed(self) -> None:
        """O sdist também: quem instala a partir dele precisa do mesmo marcador."""
        self._pular_sem_build()
        sdists = sorted(self.saida.glob("*.tar.gz"))
        self.assertEqual(len(sdists), 1, f"esperava 1 sdist, achei {sdists}")
        with tarfile.open(sdists[0]) as arquivo:
            nomes = arquivo.getnames()
        self.assertTrue(
            any(n.endswith("src/result_assembler/py.typed") for n in nomes),
            f"py.typed ausente no sdist: {[n for n in nomes if 'result_assembler' in n][:20]}",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
