# A2 ES 2026 – Proxy

Trabalho em grupo de Engenharia de Software (FGV) sobre o padrão de projeto
**Proxy**. Um pipeline de dados sobre cotações de ações é o problema original; a
etapa de Extração é refatorada com o padrão, e um *toy problem* independente
ensina o Proxy.

## Onde está cada item da entrega

| Item | Onde está |
|---|---|
| Implementação original (sem o padrão) | branch [`main`](https://github.com/JaimeWillianCarneiro/ES_proxy/tree/main) |
| Toy problem | branch [`toy-problem`](https://github.com/JaimeWillianCarneiro/ES_proxy/tree/toy-problem), pasta `toy_problem/` |
| Implementação refatorada (com Proxy) | branch [`Aplication_Proxy`](https://github.com/JaimeWillianCarneiro/ES_proxy/tree/Aplication_Proxy), classe `FonteDadosProxy` em `src/pipeline_proxy/extracao/proxy_fonte.py` |
| Instruções de execução | seção [Como executar](#como-executar) |
| Gravação da apresentação | enviada por e-mail, junto com o código |
| Enunciado | [`docs/enunciado.pdf`](docs/enunciado.pdf) |

---

## Como executar

> **Não é preciso ter chave de API.** O `.env.example` já vem com a chave pública
> `demo` e o símbolo `IBM`, suficientes para reproduzir tudo abaixo. Os testes e o
> toy problem rodam sem internet depois que as dependências estão instaladas.

### 0. Preparação (uma vez só)

Requisitos: [Git](https://git-scm.com/),
[uv](https://docs.astral.sh/uv/getting-started/installation/) e Python ≥ 3.12.

```bash
git clone https://github.com/JaimeWillianCarneiro/ES_proxy.git
cd ES_proxy
cp .env.example .env
uv sync
```

Todos os comandos são executados na raiz do repositório. O `.env` não é
versionado, então continua valendo ao trocar de branch.

### 1. Implementação original (branch `main`)

```bash
git checkout main
uv run pytest            # testes, sem internet
uv run python main.py    # pipeline completo, usa a API
```

Cada execução de `main.py` gasta uma requisição por símbolo. Rodando duas vezes
seguidas, as **duas** terminam com `chamadas_reais=1`.

<details>
<summary>Exemplo de saída (valores e datas mudam com o mercado)</summary>

```
       IBM:  100 linhas de 2026-07-07 a 2026-11-24
limpeza: 0 duplicadas removidas, 0 valores imputados, 0 linhas inválidas, 1 outliers

--- Métricas de Avaliação (IBM) ---
    random_walk: MAE = 4.3454 | RMSE = 8.7752
    media_movel: MAE = 7.3618 | RMSE = 13.6576
carga: 100 registros inseridos/atualizados no SQLite
visualizacao: 2 arquivos gerados em dados
chamadas_reais=1
tempo[extracao]=1.093s
tempo[transformacao]=0.010s
tempo[carga]=0.002s
tempo[modelagem]=0.003s
tempo[visualizacao]=0.421s
```

</details>

Arquivos gerados em `dados/`: `cotacoes.db` (SQLite), `previsoes.csv`,
`grafico_IBM.png` e `estado.json`.

### 2. Toy problem (branch `toy-problem`)

```bash
git checkout toy-problem
uv run python -m toy_problem.demo             # demonstração
uv run pytest tests/test_toy_problem.py       # testes
```

A demonstração mostra a criação adiada (a primeira exibição leva cerca de 1 s e a
segunda é imediata) e o bloqueio por permissão antes de carregar a imagem.

### 3. Implementação refatorada (branch `Aplication_Proxy`)

O proxy é ligado pela variável `USAR_PROXY` (o padrão é `false`).

Linux, macOS ou Git Bash:

```bash
git checkout Aplication_Proxy
uv run pytest                                 # testes, sem internet
USAR_PROXY=false uv run python main.py        # cliente direto
USAR_PROXY=true  uv run python main.py        # proxy, cache vazio
USAR_PROXY=true  uv run python main.py        # proxy, lê do cache
```

Windows (PowerShell):

```powershell
git checkout Aplication_Proxy
uv run pytest
$env:USAR_PROXY="false"; uv run python main.py
$env:USAR_PROXY="true";  uv run python main.py
uv run python main.py
```

Resultado esperado, sem falhas de rede:

| Execução | `chamadas_reais` | Log |
|---|---:|---|
| Cliente direto | 1 | `[API] ...` |
| Proxy, cache vazio | 1 | `[PROXY] cache miss` e depois `[API] ...` |
| Proxy, com cache | **0** | `[PROXY] cache hit` |

As métricas são as mesmas nas três execuções. O teste
`tests/test_pipeline_proxy.py` verifica isso, comparando métricas e
`previsoes.csv` com e sem proxy.

Para repetir a demonstração a partir do cache vazio, apague `dados/cache/` (a
validade do cache é de 12 horas).

### Problemas comuns

| Sintoma | O que fazer |
|---|---|
| Erro de limite por segundo | espere alguns segundos e rode de novo (o plano gratuito aceita cerca de 1 requisição por segundo) |
| Cota diária esgotada | o limite é de 25 requisições por dia; os testes e o toy problem continuam funcionando |
| Erro com outro símbolo | a chave `demo` só aceita `IBM`; para outras ações, use a sua chave (seção abaixo) |

---

## Configuração e chave de API (opcional)

Só é necessário para analisar outras ações, como `PETR4.SAO`.

1. Peça uma chave gratuita em https://www.alphavantage.co/support/#api-key (não
   pede cartão).
2. Coloque-a no `.env`. **Nunca faça commit desse arquivo.**

| Variável | Exemplo | Significado |
|---|---|---|
| `ALPHAVANTAGE_API_KEY` | `ABC123...` | sua chave |
| `SIMBOLOS` | `PETR4.SAO,VALE3.SAO` | ações a baixar (as da B3 usam o sufixo `.SAO`) |
| `MODO` | `completa` / `incremental` | tudo, ou só datas novas desde a última execução |
| `USAR_PROXY` | `true` / `false` | liga o proxy (só na branch `Aplication_Proxy`) |

A lista completa está em [`.env.example`](.env.example).

## O pipeline

**Pergunta analítica:** dá para prever o preço de fechamento de amanhã de uma
ação a partir do histórico diário?

| Etapa | O que faz |
|---|---|
| 1. Extração | baixa o histórico diário da Alpha Vantage (últimos ~100 pregões no plano gratuito) |
| 2. Transformação | remove duplicadas, imputa faltantes, escala o volume; **marca** linhas inválidas e outliers sem removê-los |
| 3. Carga | grava os dados limpos em SQLite (upsert) |
| 4. Modelagem | random walk × médias móveis, métricas MAE/RMSE |
| 5. Visualização | gráfico real × previsto (PNG) e CSV |

### Papéis do Proxy na implementação refatorada

| Papel | Classe | Responsabilidade |
|---|---|---|
| Subject | `FonteDados` | interface comum: `buscar_diario(...)` |
| RealSubject | `AlphaVantageClient` | acessa a API |
| Proxy | `FonteDadosProxy` | valida o formato da chave, usa o cache, cria o cliente só quando precisa e repete falhas transitórias |
| Cliente | `EtapaExtracao` | depende só de `FonteDados`; não muda com o proxy |

## Estrutura do código

```
main.py                    # monta e executa o pipeline
src/pipeline_proxy/
├── extracao/              # etapa 1: interface, cliente da API, extrator, estado
│   └── proxy_fonte.py     #   FonteDadosProxy (só na branch Aplication_Proxy)
├── transformacao/         # etapa 2: limpeza e escala do volume
├── carga/                 # etapa 3: SQLite
├── modelagem/             # etapa 4: modelos e métricas
├── visualizacao/          # etapa 5: gráficos e CSV
├── nucleo/etapa.py        # contrato comum das etapas e orquestrador
├── dominio.py             # formato dos dados que passam entre as etapas
├── erros.py · config.py
toy_problem/               # exemplo didático (só na branch toy-problem)
tests/                     # testes com respostas da API salvas em arquivo
```
