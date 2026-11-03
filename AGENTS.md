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

**Etapa 1 — Extração: implementada, do jeito normal (sem proxy).**

- `uv run pytest` → 24 testes passando, offline (fixtures em `tests/fixtures/`).
- `uv run python main.py` → busca a série e imprime linhas por símbolo,
  intervalo de datas, `chamadas_reais` e `tempo[extracao]`.
  Testado com `IBM` (chave `demo`) e `PETR4.SAO` (chave própria): 100 pregões, 1 chamada real.
- **Toda execução faz uma requisição nova por símbolo** (não há cache nem banco).
  O cache é a tarefa A; o banco é a Carga (etapa 3).
- O único arquivo gravado é `dados/estado.json` (última data extraída por
  símbolo, usada pelo modo incremental).

### Como o código está organizado

```
ES_proxy/
├── main.py                       # criar_fonte(): ÚNICO lugar que escolhe a FonteDados
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
│   ├── transformacao/            # vazio — etapa 2
│   ├── carga/                    # vazio — etapa 3
│   ├── modelagem/                # vazio — etapa 4
│   └── visualizacao/             # vazio — etapa 5
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
  trabalho da Transformação.
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

**Depende de:** etapa 2 (Transformação) pronta no `main`.

- Criar `transformacao/proxy_escala.py` com um `EscalaProxy` que tem a mesma
  interface do escalador usado na Transformação e só repassa a chamada para ele.
- Usar o proxy no lugar do escalador real (por flag no `.env`, como na tarefa A).
- **Mostrar na demo que nada muda:** mesma saída (um teste comparando os
  DataFrames), mesmo tempo e nenhuma das razões do Proxy presente (sem rede, sem
  cota, sem permissão, criar o objeto real é trivial). É indireção sem função.
- Ponto para a apresentação: se o objetivo for poder trocar a técnica de
  escala, o padrão certo é o **Strategy**, não o Proxy.

---

## Pipeline normal — próximas etapas (no `main`, sem proxy)

### 2. Transformação e Limpeza — `transformacao/`

`EtapaTransformacao`: `list[LoteExtracao] -> pd.DataFrame` limpo (todos os símbolos juntos).

Ordem sugerida:
1. **Deduplicação** por `(simbolo, data)`, mantendo a última ocorrência.
2. **Validação:**
   - `high >= max(open, close)`, `low <= min(open, close)`, `volume >= 0`;
   - datas crescentes por símbolo;
   - linha inválida é **marcada** (coluna `valida`), não removida.
3. **Imputação:**
   - forward-fill só em valores `NaN` (não interpolar preço);
   - não criar linhas para feriados ou fins de semana.
4. **Outliers:** `retorno = close.pct_change()` por símbolo; `|z| > 3` → coluna `outlier = True` (marcar, não remover).
5. **Escala:** `log_volume = log1p(volume)`, feita por um objeto escalador (ex.:
   `EscalaLog` / `EscalaMinMax`) recebido no construtor. É nesse ponto que a
   tarefa B vai encaixar o proxy ruim.
6. **Codificação:** dia da semana cíclico (`dia_sen`, `dia_cos`), se for usado como feature.

**Testes:**
- criar fixtures "sujas" em `tests/fixtures/`, porque a da IBM está limpa: linhas duplicadas, `high < low`, `NaN` e um salto de preço;
- testar cada passo isolado e a etapa inteira.

**Pronto quando:**
- `main.py` roda `Pipeline([EtapaExtracao(...), EtapaTransformacao(...)])`;
- o resumo mostra quantas linhas foram deduplicadas, marcadas como inválidas e como outliers.

### 3. Carga — `carga/`

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
    EtapaTransformacao(escala, ...),  # escala = real (main) ou EscalaProxy (proxy-ruim)
    EtapaCarga(...),
    EtapaModelagem(...),
    EtapaVisualizacao(...),
])
```
