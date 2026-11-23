# ES_proxy — Pipeline de dados para demonstrar o padrão Proxy

Trabalho de Engenharia de Software (FGV). Um pipeline de dados de ponta a ponta
sobre cotações de ações serve de cenário para mostrar **um bom uso** do padrão
Proxy (na Extração) e **um uso inadequado** (na Transformação), acompanhado de
um *toy problem* didático para apresentar o padrão.

**Pergunta analítica:** dá para prever o preço de fechamento de amanhã de uma
ação (ex.: PETR4) a partir do histórico diário?

## Pipeline

| Etapa | O que faz | Status |
|---|---|---|
| 1. Extração | baixa o histórico diário da Alpha Vantage | ✅ pronta (sem proxy na `main`) |
| 2. Transformação e limpeza | duplicatas, faltantes, validação, outliers, escala do volume | ✅ pronta |
| 3. Carga | grava os dados limpos em SQLite (upsert) | ✅ pronta |
| 4. Modelagem | random walk × médias móveis, métricas MAE/RMSE | ✅ pronta |
| 5. Visualização | gráfico real × previsto (PNG) + CSV | ✅ pronta |

## Branches

Cada parte da apresentação está organizada em uma branch dedicada:

| Branch | Conteúdo | Parte do Trabalho |
|---|---|---|
| `main` | pipeline completo, **sem proxy** (o "antes") | Parte 1 — Problema original |
| `toy-problem` | exemplo didático isolado (`toy_problem/`: Visualizador de Imagens Pesadas com Proxy Virtual e de Proteção) | Parte 2 — Explicação do padrão |
| `Aplication_Proxy` | `main` + `FonteDadosProxy` na Extração (cache em disco, validação da chave, lazy loading, retry) | Parte 3 — Aplicação ao original |
| `proxy-ruim` | (opcional) `main` + `EscalaProxy` na Transformação que só repassa a chamada (indireção sem função) | Parte 4 — Avaliação crítica |

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

### 1. Pipeline original (`main`) e refatorado (`Aplication_Proxy`)

```bash
uv sync                     # instala as dependências
cp .env.example .env        # depois edite o .env com a sua chave
uv run pytest               # testes (offline, não gastam cota)
uv run python main.py       # roda o pipeline