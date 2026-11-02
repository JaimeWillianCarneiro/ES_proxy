import json

import pandas as pd

from fakes import FonteFake, carregar_fixture
from pipeline_proxy.config import PoliticaRetry
from pipeline_proxy.dominio import LoteExtracao
from pipeline_proxy.nucleo.etapa import Pipeline


def test_lote_sobrevive_ida_e_volta_em_json():
    lote = FonteFake(carregar_fixture("daily_ibm.json")).buscar_diario("IBM")

    restaurado = LoteExtracao.from_dict(json.loads(json.dumps(lote.to_dict())))

    pd.testing.assert_frame_equal(restaurado.dados, lote.dados)
    assert restaurado.simbolo == lote.simbolo
    assert restaurado.tamanho == lote.tamanho
    assert restaurado.extraido_em == lote.extraido_em


def test_politica_retry_cresce_e_respeita_maximo():
    politica = PoliticaRetry(tentativas=5, backoff_base_s=1, backoff_max_s=5)

    assert [politica.espera(i) for i in range(5)] == [1, 2, 4, 5, 5]


class Somar:
    def __init__(self, nome, n):
        self.nome, self._n = nome, n

    def executar(self, entrada):
        return entrada + self._n


def test_pipeline_encadeia_etapas_e_mede_tempo():
    pipeline = Pipeline([Somar("a", 1), Somar("b", 10)])

    assert pipeline.executar(0) == 11
    assert set(pipeline.tempos_s) == {"a", "b"}
