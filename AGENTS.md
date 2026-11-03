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

## Organização do trabalho (branches)

O projeto mantém versões **sem** e **com** proxy, para dar para comparar lado a lado:

| Branch | Conteúdo | Quem |
|---|---|---|
| `main` | Pipeline "normal", **sem nenhum proxy**. Cada etapa nova entra aqui primeiro. | todos |
| `proxy-bom` | Sai do `main` e acrescenta o `FonteDadosProxy` na Extração (tarefa A). | pessoa da tarefa A |
| `proxy-ruim` | Sai do `main` (depois que a Transformação existir) e acrescenta o `EscalaProxy` (tarefa B). | pessoa da tarefa B |

Regras:
- **Não colocar código de proxy no `main`.** O `main` é o "antes" da demonstração.
- Quando o `main` ganhar etapas novas, atualizar as branches de proxy com
  `git merge main` (ou `git rebase main`).
- Opcional para a apresentação: uma branch `com-proxies` que junta as duas.

---

## Como começar

```bash
uv sync                          # instala dependências (Python >= 3.12)
cp .env.example .env             # e colocar a sua chave
uv run pytest                    # testes, offline (não gastam cota)
uv run python main.py            # roda o pipeline contra a API real
```

- Chave gratuita (sem cartão): https://www.alphavantage.co/support/#api-key
- A chave `demo` funciona só com `SIMBOLOS=IBM` (bom para testar sem gastar cota).
- Documentação da API: https://www.alphavantage.co/documentation/

---

## Estado atual do `main` (03/11/2026)

| Etapa | Situação |
|---|---|
| 1. Extração | ✅ pronta, do jeito normal (sem proxy) |
| 2. Transformação e limpeza | ✅ pronta, versão básica (sem proxy) |
| 3. Carga | ⏳ próxima |
| 4. Modelagem | ⏳ |
| 5. Visualização | ⏳ |

- `uv run pytest` → 41 testes passando, offline (fixtures em `tests/fixtures/`).
- `uv run python main.py` → roda `Pipeline([EtapaExtracao, EtapaTransformacao])`
  e imprime linhas por símbolo, o resumo da limpeza, `chamadas_reais` e o tempo
  de cada etapa. Exemplo real com `PETR4.SAO`: 100 linhas, 0 duplicadas,
  0 imputadas, 0 inválidas, 2 outliers marcados.
- **Toda execução faz uma requisição nova por símbolo** (não há cache nem banco).
  O cache é a tarefa A; o banco é a Carga (etapa 3).
- O único arquivo gravado é `dados/estado.json` (última data extraída por
  símbolo, usada pelo modo incremental).
- O resultado da limpeza ainda **não é salvo**: só vive em memória até a Carga existir.

### Como o código está organizado

```
ES_proxy/
├── main.py                       # monta o pipeline: escolhe a FonteDados e a Escala de cada etapa
├── .env.example                  # copiar para .env (chave, símbolos, modo, retry)
├── src/pipeline_proxy/
│   ├── config.py                 # Config + PoliticaRetry (já pronta para o proxy usar)
│   ├── dominio.py                # schema OHLCV, LoteExtracao, enums
│   ├── erros.py                  # ErroTransitorio / ErroPermanente e subclasses
│   ├── nucleo/etapa.py           # contrato Etapa + Pipeline (mede tempo por etapa)
│   ├── extracao/
│   │   ├── fonte.py              # FonteDados          (Subject)
│   │   ├── alpha_vantage.py      # AlphaVantageClient  (RealSubject)
│   │   ├── estado.py             # watermark do modo incremental
│   │   └── extrator.py           # EtapaExtracao (só conhece FonteDados)
│   ├── transformacao/
│   │   ├── limpeza.py            # funções puras: deduplicar, imputar, marcar inválidas/outliers
│   │   ├── escala.py             # Escala (ABC), EscalaLog, EscalaMinMax
│   │   └── etapa.py              # EtapaTransformacao + ResumoTransformacao + COLUNAS_LIMPAS
│   ├── carga/                    # vazio — etapa 3
│   ├── modelagem/                # vazio — etapa 4
│   └── visualizacao/             # vazio — etapa 5
├── dados/                        # gerado em runtime (no .gitignore)
└── tests/                        # fakes.py (FonteFake) + testes por etapa
```

### Contratos que as próximas etapas devem respeitar

- **Etapa:** toda etapa tem `nome` e `executar(entrada) -> saida`; o `Pipeline`
  encadeia a saída de uma na entrada da próxima.
- **Dados brutos:** a Extração devolve `list[LoteExtracao]`; cada lote tem um
  DataFrame com colunas `simbolo, data, open, high, low, close, volume`
  (tipos fixos, ordenado por data). Chave natural: `(simbolo, data)`.
- **A Extração não limpa nada** (não deduplica, não imputa, não valida). Isso é
  trabalho da Transformação.
- **Dados limpos:** a Transformação devolve **um** `pd.DataFrame` com todos os
  símbolos, ordenado por `(simbolo, data)`, sem duplicatas, com as colunas
  `COLUNAS_LIMPAS` = brutas + `valida` (bool), `retorno` (variação diária do
  close, NaN na 1ª linha de cada símbolo), `outlier` (bool) e `volume_escalado`.
  Nenhuma linha é removida além das duplicadas: inválidas e outliers são só
  **marcados**, e cabe a quem consome decidir se filtra.
  Contagens ficam em `EtapaTransformacao.resumo` (`ResumoTransformacao`).
- **Erros:** `ErroTransitorio` (inclui `ErroLimiteRequisicoes`) = vale repetir;
  `ErroPermanente` (inclui `ErroAutenticacao`, `ErroCotaEsgotada`) = não vale.
  A Alpha Vantage responde HTTP 200 mesmo em erro; a mensagem vem no corpo.

### Convenções

- Nomes de classes, funções e variáveis em português.
- Interfaces como `ABC` (ex.: `FonteDados`, `RepositorioEstado`); dependências
  recebidas no construtor (nada de instanciar a dependência lá dentro).
- Testes nunca acessam a internet: usar `tests/fakes.py` e `tests/fixtures/`
  (HTTP mockado com `responses`).
- Logs com prefixo curto (`[API] ...`) para a demo ficar legível.
- Commits no formato `tipo(escopo): descrição` (`feat`, `test`, `docs`, `chore`).

### Fatos da Alpha Vantage descobertos na prática

- Free tier: 25 requisições/dia, burst de 1 requisição/segundo.
- `outputsize=full` e `TIME_SERIES_DAILY_ADJUSTED` são **premium**; o gratuito
  dá os ~100 últimos pregões (`compact`, o padrão). O cliente só envia
  `outputsize` quando é `full`.
- A chave `demo` só aceita a URL exata da documentação e só funciona com `IBM`.
- Ações da B3 usam o sufixo `.SAO` (`PETR4.SAO`), não `.SA`.

---

## Tarefa A — Proxy BOM na Extração (branch `proxy-bom`)

**Por que aqui faz sentido:** a Alpha Vantage tem as três razões clássicas do Proxy:
- **Autenticação:** exige API key.
- **Custo:** 25 chamadas/dia.
- **Latência:** rede real, que pode falhar.

**O que já está pronto no `main` para isso:**
- interface `FonteDados`;
- `criar_fonte()` em `main.py` como único ponto de troca;
- erros classificados em transitório e permanente;
- `PoliticaRetry` em `config.py`;
- `LoteExtracao.to_dict()`/`from_dict()` para o cache;
- `AlphaVantageClient.chamadas_reais` para a demo;
- a sessão HTTP criada no `__init__` do cliente, um custo real que o lazy loading evita.

**Sugestão de implementação:** `extracao/proxy_fonte.py` com
`FonteDadosProxy(FonteDados)`, mesma interface do cliente real:

- **Protection:** chave vazia ou com formato inválido → `ErroAutenticacao`
  antes de qualquer chamada.
- **Caching:** guarda o `LoteExtracao` bruto em `dados/cache/`, chave
  `(simbolo, tamanho)`, com validade (ex.: 12h). Cache hit → não chama a API.
- **Virtual (lazy):** recebe uma *factory* do cliente real e só o cria no
  primeiro cache miss.
- **Retry:** repete só `ErroTransitorio`, usando `PoliticaRetry.espera(i)`;
  `ErroPermanente` sobe direto.
- Ligar por `USAR_PROXY=true` no `.env`, dentro de `criar_fonte()`.
- **Não deve mudar:** `EtapaExtracao`, `AlphaVantageClient`, `Pipeline` (esse é o argumento da apresentação).

**Pronto quando:**
- os testes cobrem estes casos: 2ª chamada sai do cache; cache vencido chama de
  novo; cliente não é criado se tudo vier do cache; chave vazia é barrada; retry
  recupera de falha transitória; erro permanente não é repetido;
- a demo roda 2× com o proxy: a 1ª com `chamadas_reais=1`, a 2ª com `chamadas_reais=0`.

---

## Tarefa B — Proxy RUIM na Transformação (branch `proxy-ruim`)

**Pode começar:** a Transformação já existe no `main`. Mas o combinado é
fazer os proxies **só depois que o pipeline inteiro estiver pronto** no `main`.

- O ponto de encaixe já existe: `EtapaTransformacao(escala_volume=...)` em
  `main.py` recebe um objeto `Escala` (`transformacao/escala.py`). Hoje é
  `EscalaLog()`.
- Criar `transformacao/proxy_escala.py` com `EscalaProxy(Escala)`, que guarda
  uma `EscalaLog` e só repassa `transformar()` para ela.
- Usar o proxy no lugar do escalador real (por flag no `.env`, como na tarefa A).
  **Não deve mudar:** `EtapaTransformacao` e `limpeza.py`.
- **Mostrar na demo que nada muda:** mesma saída (um teste comparando os
  DataFrames), mesmo tempo e nenhuma das razões do Proxy presente (sem rede, sem
  cota, sem permissão, criar o objeto real é trivial). É indireção sem função.
- Ponto para a apresentação: se o objetivo for poder trocar a técnica de
  escala, o padrão certo é o **Strategy**, e ele **já está lá**: `Escala` com
  `EscalaLog`/`EscalaMinMax` intercambiáveis. O proxy não acrescenta nada.

---

## Pipeline normal — próximas etapas (no `main`, sem proxy)

### 2. ✅ Transformação e Limpeza — `transformacao/` (versão básica concluída)

`EtapaTransformacao(escala_volume, limiar_outlier_z=3.0)`:
`list[LoteExtracao] -> pd.DataFrame` limpo (todos os símbolos juntos).

Ordem implementada (`etapa.py`, funções em `limpeza.py`):
1. **Juntar** os lotes num só DataFrame (`juntar_lotes`).
2. **Deduplicar** por `(simbolo, data)`, mantendo a última ocorrência.
3. **Imputar:** forward-fill só em preços `NaN`, por símbolo. Não cria linhas
   para feriados ou fins de semana e não interpola.
4. **Validar:** `high >= max(open, close)`, `low <= min(open, close)`,
   `volume >= 0` e preços preenchidos → coluna `valida` (marca, não remove).
5. **Outliers:** `retorno = close.pct_change()` por símbolo; `|z| > 3` →
   coluna `outlier` (marca, não remove).
6. **Escalar** o volume com a `Escala` recebida → `volume_escalado`.

Testes em `tests/test_transformacao.py`. Os dados sujos (duplicadas, `NaN`,
`high < open`, salto de preço) são montados no próprio teste com `criar_lote()`,
porque a resposta da API (um JSON indexado por data) não consegue ter duplicatas.

Limitações conhecidas (melhorias futuras, se quiserem):
- No modo `incremental` só chegam os dias novos, então o `retorno` do 1º dia
  novo fica `NaN` e o z-score usa poucos pontos. Isso se resolve quando a Carga
  existir: dá para ler o histórico do banco.
- Não verifica "buracos" de datas (pregões faltando); a validação é por linha.
- Codificação de dia da semana (seno/cosseno) ficou para a Modelagem, se for usada como feature.

### 3. Carga — `carga/` (próximo passo)

`EtapaCarga`: recebe o `pd.DataFrame` limpo da Transformação (`COLUNAS_LIMPAS`)
e devolve o que a Modelagem vai consumir (sugestão: o DataFrame lido de volta do
banco, com todo o histórico do símbolo, não só o lote atual).

- SQLite em `dados/pipeline.sqlite`, tabela `cotacoes` com
  `PRIMARY KEY (simbolo, data)`.
- Modo de escrita: **upsert** (`INSERT ... ON CONFLICT DO UPDATE`) → rodar de
  novo não duplica.
- A partir daqui, a modelagem lê do banco, sem precisar da API.
- Mover a watermark para depois da gravação (ou trocar `RepositorioEstadoJson`
  por um que lê `MAX(data)` do banco) — ver `TODO(carga)` em `extrator.py`.
- O banco (dado limpo, permanente) é diferente do cache da tarefa A (resposta
  bruta, temporária): ficam em arquivos separados.

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
    EtapaExtracao(fonte, estado),     # fonte = cliente real (main) ou proxy (proxy-bom)
    EtapaTransformacao(escala_volume),  # EscalaLog (main) ou EscalaProxy (proxy-ruim)
    EtapaCarga(...),
    EtapaModelagem(...),
    EtapaVisualizacao(...),
])
```
