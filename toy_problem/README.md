# Toy Problem — Padrão de Projeto Proxy (Visualizador de Imagens Pesadas)

Exemplo didático independente do pipeline principal para demonstrar o funcionamento,
os participantes, as vantagens e as limitações do padrão **Proxy** (Parte 2 do trabalho)[cite: 3, 6].

## 1. Problema que o Padrão Resolve

Carregar e decodificar imagens de alta resolução (`ImagemReal`) consome tempo e memória
logo na criação do objeto. Em uma galeria com dezenas de arquivos, instanciar tudo
antecipadamente desperdiça recursos caso o usuário abra apenas uma imagem ou nem tenha
permissão de acesso.

## 2. Participantes e Responsabilidades

| Papel GoF | Classe / Função | Responsabilidade |
|---|---|---|
| **Subject** | `Imagem` (`visualizador.py`) | Define o contrato comum (`exibir() -> str`) consumido pelo cliente. |
| **RealSubject** | `ImagemReal` (`visualizador.py`) | Realiza o trabalho pesado (simula carregamento custoso no `__init__`). |
| **Proxy** | `ImagemProxy` (`visualizador.py`) | Mantém a mesma interface `Imagem`, controla permissão (**Proteção**) e instancia `ImagemReal` apenas na 1ª chamada a `exibir()` (**Virtual**). |
| **Client** | `renderizar_galeria` (`demo.py`) | Interage apenas com a abstração `Imagem`, sem saber se usa o objeto real ou o proxy. |

## 3. Como Executar

Na raiz do repositório:

```bash
uv run python -m toy_problem.demo
uv run pytest tests/test_toy_problem.py