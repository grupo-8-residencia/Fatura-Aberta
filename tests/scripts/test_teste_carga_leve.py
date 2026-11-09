"""Falhas de rede devem aparecer no resumo, sem interromper o teste de carga."""

import pytest
import teste_carga_leve as carga


def test_timeout_ao_ler_resposta_conta_como_falha(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class RespostaComTimeout:
        status = 200

        def __enter__(self) -> "RespostaComTimeout":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            raise TimeoutError("tempo esgotado")

    monkeypatch.setattr(carga, "urlopen", lambda *_args, **_kwargs: RespostaComTimeout())

    assert carga.main(["--requisicoes", "1", "--concorrencia", "1"]) == 1
    saida = capsys.readouterr().out
    assert "Sucesso: 0/1" in saida
    assert "Meta: 100% de sucesso" in saida
    assert "não atingida" in saida
