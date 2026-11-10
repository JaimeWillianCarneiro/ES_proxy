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
| 4. Modelagem | random walk × médias móveis, métricas MAE/RMSE | ⏳ próxima |
| 5. Visualização | gráfico real × previsto (PNG/HTML) + CSV | ⏳ |

## Branches

| Branch | Conteúdo |
|---|---|
| `main` | pipeline "normal", **sem proxy** (o "antes") |
| `proxy-bom` | `main` + proxy na Extração (cache, validação da chave, lazy loading, retry) |
| `proxy-ruim` | `main` + proxy na Transformação que só repassa a chamada (indireção sem função) |

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
 PETR4.SAO:  100 linhas de 2026-06-11 a 2026-10-30
limpeza: 0 duplicadas removidas, 0 valores imputados, 0 linhas inválidas, 2 outliers
chamadas_reais=1
tempo[extracao]=0.589s
tempo[transformacao]=0.008s
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
