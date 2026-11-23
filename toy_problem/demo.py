"""Demonstração executável da Parte 2 (Toy Problem — Padrão Proxy).

Execute com:
    uv run python -m toy_problem.demo
"""

from __future__ import annotations

import time

from toy_problem.visualizador import ErroAcessoImagem, Imagem, ImagemProxy


def renderizar_galeria(imagens: list[Imagem]) -> None:
    """Cliente: depende apenas da interface `Imagem` (Subject)."""
    for img in imagens:
        print(" ->", img.exibir())


def main() -> None:
    print("=== 1. Instanciando proxies (Proxy Virtual: custo zero na criação) ===")
    t0 = time.perf_counter()
    foto_publica = ImagemProxy("mapa_satelite_8k.tiff", perfil_usuario="editor", tempo_carregamento_s=1.0)
    foto_restrita = ImagemProxy("planta_confidencial.tiff", perfil_usuario="visitante", tempo_carregamento_s=1.0)
    foto_nao_aberta = ImagemProxy("backup_historico.tiff", perfil_usuario="admin", tempo_carregamento_s=1.0)
    print(f"3 proxies criados em {(time.perf_counter() - t0):.4f}s")
    print(f"foto_publica.carregada = {foto_publica.carregada}")
    print(f"foto_nao_aberta.carregada = {foto_nao_aberta.carregada}\n")

    print("=== 2. Proxy de Proteção: bloqueio antes de carregar objeto pesado ===")
    t0 = time.perf_counter()
    try:
        foto_restrita.exibir()
    except ErroAcessoImagem as erro:
        print(f"Bloqueado imediatamente em {(time.perf_counter() - t0):.4f}s: {erro}")
        print(f"foto_restrita.carregada = {foto_restrita.carregada}\n")

    print("=== 3. Primeira exibição (Cache/Lazy Miss: carrega ImagemReal agora) ===")
    t0 = time.perf_counter()
    renderizar_galeria([foto_publica])
    print(f"Tempo da 1ª exibição: {(time.perf_counter() - t0):.4f}s | carregada = {foto_publica.carregada}\n")

    print("=== 4. Segunda exibição (RealSubject já está em memória: instantâneo) ===")
    t0 = time.perf_counter()
    renderizar_galeria([foto_publica])
    print(f"Tempo da 2ª exibição: {(time.perf_counter() - t0):.4f}s | carregada = {foto_publica.carregada}")
    print(f"foto_nao_aberta.carregada (nunca exibida) = {foto_nao_aberta.carregada}")


if __name__ == "__main__":
    main()