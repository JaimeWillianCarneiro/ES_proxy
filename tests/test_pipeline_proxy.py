from pathlib import Path
from runpy import run_path

import responses
from fakes import carregar_fixture

from pipeline_proxy.extracao.alpha_vantage import URL_BASE


def test_pipeline_preserva_previsoes_e_reutiliza_cache(tmp_path, monkeypatch, capsys):
    pasta_projeto = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "demo")
    monkeypatch.setenv("SIMBOLOS", "IBM")
    monkeypatch.setenv("MODO", "completa")
    monkeypatch.setenv("TAMANHO", "compact")
    monkeypatch.setenv("DIR_DADOS", str(tmp_path))
    payload = carregar_fixture("daily_ibm.json")
    resultados = []

    for usar_proxy, chamadas_esperadas in (
        ("false", 1), ("false", 1), ("true", 1), ("true", 0)
    ):
        monkeypatch.setenv("USAR_PROXY", usar_proxy)
        with responses.RequestsMock(assert_all_requests_are_fired=False) as http:
            http.get(URL_BASE, json=payload)
            run_path(str(pasta_projeto / "main.py"), run_name="__main__")
            assert len(http.calls) == chamadas_esperadas

        saida = capsys.readouterr().out.splitlines()
        assert f"chamadas_reais={chamadas_esperadas}" in saida
        metricas = [linha for linha in saida if "MAE =" in linha]
        assert len(metricas) == 2
        previsoes = (tmp_path / "previsoes.csv").read_bytes()
        resultados.append((metricas, previsoes))

    assert all(resultado == resultados[0] for resultado in resultados[1:])
