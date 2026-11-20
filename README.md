# ES_proxy — Pipeline de dados para demonstrar o padrão Proxy

Trabalho de Engenharia de Software (FGV). Um pipeline de dados de ponta a ponta
sobre cotações de ações serve de cenário para mostrar **um bom uso** do padrão
Proxy (na Extração) e **um uso inadequado** (na Transformação).

**Pergunta analítica:** dá para prever o preço de fechamento de amanhã de uma
ação (ex.: PETR4) a partir do histórico diário?

## Pipeline

| Etapa | O que faz | Status |
|---|---|---|
| 1. Extração | baixa o histórico diário da Alpha Vantage | ✅ pronta (sem proxy) |
| 2. Transformação e limpeza | duplicatas, faltantes, validação, outliers, escala do volume | ✅ pronta (básica, sem proxy) |
| 3. Carga | grava os dados limpos em SQLite (upsert) | ✅ pronta |
| 4. Modelagem | random walk × médias móveis, métricas MAE/RMSE | ✅ pronta |
| 5. Visualização | gráfico real × previsto (PNG/HTML) + CSV | ✅ pronta |

## Branches

| Branch | Conteúdo |
|---|---|
| `main` | pipeline "normal", **sem proxy** (o "antes") |
| `Aplication-Proxy` | 	versão refatorada, com proxy na extração habilitado por USAR_PROXY=true |
| `proxy-ruim(ideia)` | `main` + proxy na Transformação que só repassa a chamada (indireção sem função) |

Os proxies entram **só depois que o pipeline inteiro estiver pronto** no `main`.

## Fonte de dados: Alpha Vantage

- Site: https://www.alphavantage.co/ · Documentação: https://www.alphavantage.co/documentation/
- Endpoint usado: `TIME_SERIES_DAILY` → por dia: abertura, máxima, mínima,
  fechamento e volume.
- **Plano gratuito:** 25 requisições por dia e no máximo ~1 por segundo. Devolve
  os **últimos ~100 pregões** (série completa e preço ajustado são pagos).
- A API responde HTTP 200 mesmo em erro; o programa lê a mensagem no corpo e
  diferencia limite por segundo (vale tentar de novo), cota diária esgotada,
  chave inválida e símbolo inválido.

### Obtendo a chave de API (grátis, ~20 segundos)

1. Acesse https://www.alphavantage.co/support/#api-key
2. Preencha o formulário (não pede cartão) e copie a chave.
3. Coloque-a no `.env` (veja abaixo). **Nunca faça commit do `.env`** — ele já
   está no `.gitignore`.

Sem chave, dá para testar com `ALPHAVANTAGE_API_KEY=demo` e `SIMBOLOS=IBM`
(a chave `demo` só funciona com IBM).

Ações brasileiras usam o sufixo `.SAO`: `PETR4.SAO`, `VALE3.SAO`, `ITUB4.SAO`.

## Como rodar

Requer [uv](https://docs.astral.sh/uv/) e Python ≥ 3.12.

```bash
uv sync                     # instala as dependências
cp .env.example .env        # depois edite o .env com a sua chave
uv run pytest               # testes (offline, não gastam cota)
uv run python main.py       # roda o pipeline
```

Saída esperada:

```
IBM:  100 linhas de 2026-06-18 a 2026-11-09
limpeza: 0 duplicadas removidas, 0 valores imputados, 0 linhas inválidas, 1 outliers

--- Métricas de Avaliação (IBM) ---
    random_walk: MAE = 4.5857 | RMSE = 8.9199
    media_movel: MAE = 8.0599 | RMSE = 14.1340
carga: 100 registros inseridos/atualizados no SQLite
visualizacao: 2 arquivos gerados em dados
chamadas_reais=1
tempo[extracao]=0.930s
tempo[transformacao]=0.008s
tempo[carga]=0.003s
tempo[modelagem]=0.003s
tempo[visualizacao]=0.412s
```

A limpeza **marca** linhas inválidas e outliers (colunas `valida` e `outlier`),
sem removê-las; só as duplicadas são removidas.

Cada execução gasta **1 requisição por símbolo** da cota diária.

Principais variáveis do `.env` (lista completa em `.env.example`):

| Variável | Exemplo | Significado |
|---|---|---|
| `ALPHAVANTAGE_API_KEY` | `ABC123...` | sua chave |
| `SIMBOLOS` | `PETR4.SAO,VALE3.SAO` | ações a baixar |
| `MODO` | `completa` / `incremental` | tudo, ou só datas novas desde a última execução |

## Comparar o pipeline com e sem proxy
Na branch `Aplication_Proxy`, configure a chave no `.env`. Os comandos abaixo
usam IBM em modo completo e criam um diretório temporário para começar com o cache vazio.

```bash
(
    DIR_DADOS="$(mktemp -d)" || exit 1
    export DIR_DADOS SIMBOLOS=IBM MODO=completa TAMANHO=compact

    USAR_PROXY=false uv run python main.py
    USAR_PROXY=false uv run python main.py
    USAR_PROXY=true uv run python main.py
    USAR_PROXY=true uv run python main.py
)
```

Quando as consultas têm sucesso na primeira tentativa, o contador
`chamadas_reais` mostra os seguintes valores:

| Configuração | Primeira execução | Segunda execução |
|---|---:|---:|
| Cliente direto | 1 | 1 |
| Proxy | 1 | 0 |

A segunda execução com proxy reutiliza o lote bruto guardado em
`${DIR_DADOS}/cache`. O lote vale por 12 horas. Durante esse período, uma nova
cotação pode demorar a aparecer. Com os mesmos dados de entrada, o CSV e as
métricas coincidem nas duas versões.

Para testar o cache e os reintentos sem fazer chamadas à API:

```bash
uv run pytest -q tests/test_proxy_fonte.py
```

## Estrutura

```
main.py                    # monta e executa o pipeline
src/pipeline_proxy/
├── extracao/              # etapa 1 (cliente da API, extrator, estado incremental)
├── transformacao/         # etapa 2 (limpeza + escala do volume)
├── carga/ modelagem/ visualizacao/   # etapas 3–5 (a fazer)
├── nucleo/etapa.py        # contrato comum das etapas + orquestrador
├── dominio.py             # formato dos dados que passa entre as etapas
├── erros.py · config.py
tests/                     # testes com respostas reais salvas da API
```

Detalhes de arquitetura, decisões e tarefas de cada pessoa: [`AGENTS.md`](AGENTS.md).
