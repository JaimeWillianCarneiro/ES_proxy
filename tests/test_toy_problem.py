import pytest

from toy_problem.demo import renderizar_galeria
from toy_problem.visualizador import ErroAcessoImagem, ImagemProxy, ImagemReal


def test_proxy_nao_instancia_imagem_real_na_criacao():
    atrasos: list[float] = []
    proxy = ImagemProxy("foto.tiff", perfil_usuario="admin", tempo_carregamento_s=2.0, dormir=atrasos.append)

    assert not proxy.carregada
    assert atrasos == []


def test_proxy_virtual_carrega_apenas_na_primeira_exibicao():
    atrasos: list[float] = []
    proxy = ImagemProxy("foto.tiff", perfil_usuario="editor", tempo_carregamento_s=2.0, dormir=atrasos.append)

    saida_1 = proxy.exibir()
    saida_2 = proxy.exibir()

    assert proxy.carregada
    assert atrasos == [2.0]  # carregou uma única vez
    assert saida_1 == "Exibindo <Pixels 8K de 'foto.tiff'>"
    assert saida_2 == saida_1


def test_proxy_protecao_bloqueia_usuario_sem_permissao_sem_carregar():
    atrasos: list[float] = []
    proxy = ImagemProxy("secreto.tiff", perfil_usuario="visitante", tempo_carregamento_s=2.0, dormir=atrasos.append)

    with pytest.raises(ErroAcessoImagem):
        proxy.exibir()

    assert not proxy.carregada
    assert atrasos == []


def test_cliente_funciona_com_real_e_proxy_indistintamente(capsys):
    real = ImagemReal("a.tiff", tempo_carregamento_s=1.0, dormir=lambda _: None)
    proxy = ImagemProxy("b.tiff", perfil_usuario="admin", tempo_carregamento_s=1.0, dormir=lambda _: None)

    renderizar_galeria([real, proxy])
    saida = capsys.readouterr().out

    assert "Exibindo <Pixels 8K de 'a.tiff'>" in saida
    assert "Exibindo <Pixels 8K de 'b.tiff'>" in saida
