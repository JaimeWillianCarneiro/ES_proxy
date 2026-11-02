# Spec: Pipeline de Dados para Demonstração do Design Pattern Proxy

## Contexto e motivação

Apresentação de design pattern (Proxy) na disciplina de Engenharia de Software,
usando como estudo de caso um pipeline de dados de ponta a ponta: extração de
uma série temporal financeira, limpeza, carga, modelagem simples e
visualização. O objetivo é mostrar, no mesmo pipeline, um ponto onde o Proxy
agrega valor real (Extração) e um ponto onde ele é um mau uso do padrão
(Transformação) — contraste pedagógico.

**Pergunta analítica:** prever o fechamento do dia seguinte de uma ação da B3
(ex.: `PETR4.SAO`) a partir do histórico diário, comparando um baseline
"burro" (random walk) com médias móveis.

---

## Estado atual (02/11/2026)

**Etapa 1 — Extração: implementada, sem proxy.**

- `uv run pytest` → 24 testes passando, offline (fixtures em `tests/fixtures/`).
- `uv run python main.py` → busca a série na Alpha Vantage e imprime o resumo.
  Testado com `IBM` (chave `demo`) e `PETR4.SAO` (chave própria): 100 pregões,
  1 chamada real.
- **Ainda não há persistência dos dados nem cache:** toda execução faz uma
  requisição nova por símbolo. Isso é intencional: é o "antes" da demonstração.
  O cache vem com o proxy (passo 1) e o banco vem com a Carga (passo 3).
- O único arquivo gravado hoje é `dados/estado.json` (última data extraída por
  símbolo, usada pelo modo incremental).

### Como o código está organizado

```
ES_proxy/
├── main.py                       # criar_fonte(): ÚNICO ponto onde o proxy vai entrar
├── .env.example                  # copiar para .env (chave, símbolos, modo, retry)
├── src/pipeline_proxy/
│   ├── config.py                 # Config + PoliticaRetry
│   ├── dominio.py                # schema OHLCV, LoteExtracao, enums
│   ├── erros.py                  # ErroTransitorio / ErroPermanente e subclasses
│   ├── nucleo/etapa.py           # contrato Etapa + Pipeline (mede tempo por etapa)
│   ├── extracao/
│   │   ├── fonte.py              # FonteDados          (Subject)
│   │   ├── alpha_vantage.py      # AlphaVantageClient  (RealSubject)
│   │   ├── estado.py             # watermark do modo incremental
│   │   └── extrator.py           # EtapaExtracao (só conhece FonteDados)
│   ├── transformacao/            # vazio — passo 2
│   ├── carga/                    # vazio — passo 3
│   ├── modelagem/                # vazio — passo 4
│   └── visualizacao/             # vazio — passo 5
├── dados/                        # gerado em runtime (no .gitignore)
└── tests/                        # fakes.py (FonteFake) + testes
```

### Contratos que as próximas etapas devem respeitar

- **Etapa:** toda etapa tem `nome` e `executar(entrada) -> saida`; o `Pipeline`
  encadeia a saída de uma na entrada da próxima.
- **Dados brutos:** a Extração devolve `list[LoteExtracao]`; cada lote tem um
  DataFrame com colunas `simbolo, data, open, high, low, close, volume`
  (tipos fixos, ordenado por data). Chave natural: `(simbolo, data)`.
- **A Extração não limpa nada** (não deduplica, não imputa, não valida). Isso é
  trabalho da Transformação, onde fica o exemplo do proxy ruim.
- **Erros:** `ErroTransitorio` (inclui `ErroLimiteRequisicoes`) = vale repetir;
  `ErroPermanente` (inclui `ErroAutenticacao`, `ErroCotaEsgotada`) = não vale.
  A Alpha Vantage responde HTTP 200 mesmo em erro; a mensagem vem no corpo.

### Fatos da Alpha Vantage descobertos na prática

- Free tier: 25 requisições/dia, burst de 1 requisição/segundo.
- `outputsize=full` e `TIME_SERIES_DAILY_ADJUSTED` são **premium**; o gratuito
  dá os ~100 últimos pregões (`compact`, o padrão). O cliente só envia
  `outputsize` quando é `full`.
- A chave `demo` só aceita a URL exata da documentação e só funciona com `IBM`.
- Ações da B3 usam o sufixo `.SAO` (`PETR4.SAO`), não `.SA`.

---

## Próximos passos

### 1. Proxy BOM na Extração — `extracao/proxy_fonte.py`

`FonteDadosProxy(FonteDados)`, mesma interface do cliente real:

- **Protection:** chave vazia ou com formato inválido → `ErroAutenticacao`
  antes de qualquer chamada.
- **Caching:** guarda o `LoteExtracao` bruto (`to_dict`/`from_dict`) em
  `dados/cache/`, chave `(simbolo, tamanho)`, com validade (ex.: 12–24h).
  Cache hit → não chama a API.
- **Virtual (lazy):** recebe uma *factory* do cliente real e só o cria no
  primeiro cache miss.
- **Retry:** repete só `ErroTransitorio`, usando `PoliticaRetry.espera(i)`;
  `ErroPermanente` sobe direto.
- Ligar via `USAR_PROXY=true` no `.env`, dentro de `criar_fonte()` em `main.py`.
- Testes com `FonteFake` + contador: 2ª chamada sai do cache; retry recupera de
  falhas transitórias; não repete erro permanente; cliente não é criado se tudo
  vier do cache.
- **Demo:** rodar `main.py` duas vezes com e sem proxy e comparar
  `chamadas_reais` e `tempo[extracao]`.

### 2. Transformação e Limpeza (+ Proxy RUIM) — `transformacao/`

`EtapaTransformacao`: `list[LoteExtracao] -> DataFrame` limpo.

- Deduplicação por `(simbolo, data)`.
- Validação: `high >= max(open, close)`, `low <= min(open, close)`,
  `volume >= 0`, datas crescentes.
- Outliers: retorno diário > 3 desvios-padrão → marcar (coluna booleana), não remover.
- Imputação: forward-fill só onde faltar (não interpolar preço).
- Escala: `log(volume)`.
- Codificação: dia da semana cíclico (seno/cosseno), se usado como feature.
- **Proxy ruim:** `EscalaProxy` que só repassa para `EscalaMinMax`. Mostrar
  que nenhuma das razões do proxy se aplica (sem rede, cota, permissão ou custo
  de criação). O que faria sentido aqui, se o objetivo for variar a técnica, é
  o **Strategy**.

### 3. Carga — `carga/`

- SQLite em `dados/pipeline.sqlite`, tabela `cotacoes` com
  `PRIMARY KEY (simbolo, data)`.
- Modo de escrita: **upsert** (`INSERT ... ON CONFLICT DO UPDATE`) → rodar de
  novo não duplica.
- A partir daqui, a modelagem lê do banco, sem precisar da API.
- Mover a watermark para depois da gravação (ou trocar `RepositorioEstadoJson`
  por um que lê `MAX(data)` do banco) — ver `TODO(carga)` em `extrator.py`.
- Importante: o **cache do proxy** (resposta bruta, temporária, com validade) e
  o **banco da Carga** (dado limpo, histórico permanente) têm papéis
  diferentes e ficam em arquivos separados.

### 4. Análise e Modelagem — `modelagem/`

- **Alvo:** `close` do dia seguinte.
- **Modelos:** random walk (`ŷ[t+1] = close[t]`) → SMA(5/10/20) → EMA.
  ARIMA só se sobrar tempo (exigiria `statsmodels`).
- **Validação:** split temporal (≈80 pregões treino / 20 teste), nunca aleatório.
- **Métricas:** MAE, RMSE e acurácia direcional (acertou se sobe/desce).
- **Features:** lags do fechamento, médias móveis, volume defasado.
- **Agregação:** resample semanal opcional.
- **Balanceamento:** só se reformular como classificação ("sobe ou desce?").
- Resultado esperado (e didático): o random walk é difícil de bater.

### 5. Visualização e Entrega — `visualizacao/`

- Gráfico real × previsto (um traço por modelo) com matplotlib (PNG) ou
  plotly (HTML), em `dados/saida/`.
- Exportar também um CSV com previsões e a tabela de métricas.

### Pipeline final em `main.py`

```python
Pipeline([
    EtapaExtracao(fonte, estado),     # fonte = proxy ou cliente real
    EtapaTransformacao(...),
    EtapaCarga(...),
    EtapaModelagem(...),
    EtapaVisualizacao(...),
])
```
