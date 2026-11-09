"""Testes do kit de anotação humana e do consolidador (issue #32)."""

from __future__ import annotations

import csv
from pathlib import Path

import consolidar_anotacoes as ca
import gerar_golden_set as gs
import gerar_kit_anotacao as kit


def _linhas(conteudo: str) -> list[dict[str, str]]:
    return list(csv.DictReader(conteudo.splitlines()))


def test_kit_e_deterministico() -> None:
    assert kit.gerar_kit() == kit.gerar_kit()


def test_um_csv_por_anotador_mais_revisao() -> None:
    saida = kit.gerar_kit()
    assert set(saida) == {f"{a}.csv" for a in gs.ANOTADORES} | {kit.ARQ_REVISAO}


def test_30_itens_por_pessoa_sem_repeticao() -> None:
    saida = kit.gerar_kit()
    vistos: list[str] = []
    for nome in gs.ANOTADORES:
        linhas = _linhas(saida[f"{nome}.csv"])
        assert len(linhas) == 30
        assert sum(1 for x in linhas if x["tipo"] == "pergunta") == 12
        assert sum(1 for x in linhas if x["tipo"] == "fatura") == 18
        vistos += [x["id"] for x in linhas]
    assert len(vistos) == len(set(vistos)) == 180


def test_colunas_humanas_nascem_vazias() -> None:
    saida = kit.gerar_kit()
    for nome, conteudo in saida.items():
        for linha in _linhas(conteudo):
            for coluna in kit.COLUNAS_HUMANAS:
                assert linha[coluna] == "", (nome, linha["id"], coluna)
            assert linha["id"]


def test_revisao_tem_as_120_perguntas() -> None:
    linhas = _linhas(kit.gerar_kit()[kit.ARQ_REVISAO])
    assert len(linhas) == gs.N_PERGUNTAS
    assert len({x["id"] for x in linhas}) == gs.N_PERGUNTAS


def test_fatura_traz_itens_total_e_gabarito() -> None:
    f = gs.gerar_faturas()[0]
    linha = kit.linha_fatura(f)
    assert f["total"] in linha["enunciado"]
    assert f["itens"][0]["descricao"] in linha["enunciado"]
    assert f["gabarito_fatura"] in linha["gabarito_proposto"]


def test_kit_gravado_no_repositorio_bate_com_o_gerador(tmp_path: Path) -> None:
    kit.escrever_kit(tmp_path)
    for caminho in tmp_path.glob("*.csv"):
        assert caminho.read_text(encoding="utf-8-sig") == kit.gerar_kit()[caminho.name]
    # Os CSV versionados (se presentes e ainda sem anotação) também batem com o gerador.
    for caminho in kit.PASTA_ANOTACOES.glob("*.csv"):
        linhas = _linhas(caminho.read_text(encoding="utf-8-sig"))
        if all(not x["concorda"] for x in linhas):
            assert caminho.read_text(encoding="utf-8-sig") == kit.gerar_kit()[caminho.name]


def test_gerar_kit_nao_toca_nos_arquivos_congelados(tmp_path: Path) -> None:
    kit.escrever_kit(tmp_path)
    assert gs.verificar() == []


def _preencher(caminho: Path, respostas: dict[str, tuple[str, str, str]]) -> None:
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        leitor = csv.DictReader(f)
        colunas = list(leitor.fieldnames or [])
        linhas = list(leitor)
    for linha in linhas:
        if linha["id"] in respostas:
            linha["concorda"], linha["correcao"], linha["comentario"] = respostas[linha["id"]]
    with caminho.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=colunas)
        escritor.writeheader()
        escritor.writerows(linhas)


def test_consolidador_com_csv_vazio(tmp_path: Path) -> None:
    kit.escrever_kit(tmp_path)
    resumos = ca.consolidar(tmp_path)
    assert all(r.anotados == 0 and not r.divergencias for r in resumos)
    assert sum(len(r.pendentes) for r in resumos) == 180 + 120


def test_consolidador_com_csv_preenchido_sintetico(tmp_path: Path) -> None:
    kit.escrever_kit(tmp_path)
    alvo = tmp_path / f"{gs.ANOTADORES[0]}.csv"
    ids = [x["id"] for x in _linhas(alvo.read_text(encoding="utf-8-sig"))]
    _preencher(
        alvo,
        {
            ids[0]: ("sim", "", ""),
            ids[1]: ("Não", "correção sintética", "comentário sintético"),
            ids[2]: ("talvez", "", ""),
        },
    )
    resumo = next(r for r in ca.consolidar(tmp_path) if r.arquivo == alvo.name)
    assert resumo.anotados == 2
    assert [d["id"] for d in resumo.divergencias] == [ids[1]]
    assert resumo.divergencias[0]["correcao"] == "correção sintética"
    assert resumo.pendentes == ids[3:]
    assert len(resumo.invalidos) == 1


def test_aplicar_so_imprime_e_nao_altera_nada(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    kit.escrever_kit(tmp_path)
    alvo = tmp_path / f"{gs.ANOTADORES[1]}.csv"
    primeiro = _linhas(alvo.read_text(encoding="utf-8-sig"))[0]["id"]
    _preencher(alvo, {primeiro: ("não", "valor sintético", "")})
    antes = {c.name: c.read_bytes() for c in tmp_path.glob("*.csv")}
    assert ca.main(["--pasta", str(tmp_path), "--aplicar"]) == 0
    saida = capsys.readouterr().out
    assert primeiro in saida and "valor sintético" in saida and "Nada foi gravado" in saida
    assert antes == {c.name: c.read_bytes() for c in tmp_path.glob("*.csv")}
    assert gs.verificar() == []


def test_valor_invalido_gera_codigo_de_saida_1(tmp_path: Path) -> None:
    kit.escrever_kit(tmp_path)
    alvo = tmp_path / f"{gs.ANOTADORES[2]}.csv"
    primeiro = _linhas(alvo.read_text(encoding="utf-8-sig"))[0]["id"]
    _preencher(alvo, {primeiro: ("quem sabe", "", "")})
    assert ca.main(["--pasta", str(tmp_path)]) == 1


def test_pasta_inexistente_retorna_erro(tmp_path: Path) -> None:
    assert ca.main(["--pasta", str(tmp_path / "nao-existe")]) == 1
