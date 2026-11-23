# Trabalho em Grupo — Padrões de Projeto (Proxy)

Enunciado completo: `docs/enunciado.pdf`. **Este arquivo deve sempre seguir o enunciado.**
Em caso de dúvida, o enunciado manda.

- **Padrão escolhido:** Proxy.
- **Entrega:** até **24/11/2026, 23:59**, por e-mail para `luisbuenopro@gmail.com`,
  com o título **"A2 ES 2026 – Proxy"**.
- **Todos** os integrantes participam da apresentação e precisam saber explicar o
  código e as decisões de design.

## O que o enunciado exige

A apresentação é gravada e tem 4 partes. Em **todas**, a explicação deve apontar o
**código concreto** (classe, método, linha). Citar só princípios ou definições não vale.

| Parte | Exigência | Onde fica |
|---|---|---|
| 1. Problema original | Sistema completo, funcional e **sem** o padrão, com problemas de design **demonstráveis no código**. Explicar contexto e responsabilidades, executar, identificar os problemas, **localizar os trechos responsáveis** e suas consequências para manutenção/evolução/extensão, e justificar por que o Proxy é pertinente. | branch `main` |
| 2. Explicação do padrão | Ensinar o Proxy com um **toy problem diferente** do problema original: problema que resolve, participantes e responsabilidades, estrutura e funcionamento, **implementação funcional**, vantagens e limitações. Usar o código do exemplo. | `toy_problem/` |
| 3. Aplicação ao original | Refatorar o original com o Proxy: executar, mostrar o que mudou, **mostrar no código** quem faz cada papel, retomar cada problema da parte 1 e mostrar como foi tratado, apontar pontos de extensão, **provar que o comportamento original foi preservado**, e discutir o que aconteceria se componentes fossem modificados, substituídos ou removidos. | branch `proxy-bom` |
| 4. Avaliação crítica | Benefícios **efetivamente obtidos**, custos e complexidade introduzidos, situações em que o Proxy **não** é recomendado, limitações da solução. Baseada nas duas implementações, sem afirmações genéricas. | roteiro + (opcional) `proxy-ruim` |

> Uma melhoria só existe se for demonstrada. "Aplicar o padrão" não basta: é preciso
> mostrar o benefício obtido.

### Entregáveis (checklist)

- [ ] Gravação da apresentação
- [ ] Código-fonte executável do original (`main`) e do refatorado (`proxy-bom`)
- [ ] Código-fonte do toy problem
- [ ] Instruções para executar os programas (README)
- [ ] Nome completo e código de aluno de **todos** os participantes (arquivo `INTEGRANTES.md`)

---

## Estado atual

| Item | Situação |
|---|---|
| `main`: pipeline completo sem proxy (Extração → Transformação → Carga → Modelagem → Visualização) | ✅ pronto, `uv run pytest` passa offline |
| Parte 1: problemas de design documentados com localização no código | ⏳ ver seção "Parte 1" abaixo; **falta virar roteiro** |
| Parte 2: `toy_problem/` | ❌ não existe (outra pessoa do grupo é responsável) |
| Parte 3: responsável | **nós** (esta sessão/pessoa) |
| Parte 3: branch `proxy-bom` | ❌ não existe |
| Parte 4: roteiro da avaliação crítica | ❌ não existe |
| `INTEGRANTES.md` | ❌ não existe |

---

## Como começar

```bash
uv sync                          # instala dependências (Python >= 3.12)
cp .env.example .env             # e colocar a sua chave
uv run pytest                    # testes, offline (não gastam cota)
uv run python main.py            # roda o pipeline contra a API real
```

- Chave gratuita (sem cartão): https://www.alphavantage.co/support/#api-key
- A chave `demo` só funciona com `SIMBOLOS=IBM` (bom para testar sem gastar cota).

---

## Parte 1 — O problema original (`main`)

**Contexto:** pipeline de dados de ponta a ponta sobre uma série temporal
financeira (`PETR4.SAO`): extração da Alpha Vantage, limpeza, carga em SQLite,
modelagem (random walk × médias móveis) e visualização. Pergunta analítica:
dá para prever o fechamento do dia seguinte?

### Responsabilidades dos componentes (para explicar na gravação)

| Componente | Responsabilidade |
|---|---|
| `FonteDados` (`extracao/fonte.py`) | interface: `buscar_diario(simbolo, tamanho) -> LoteExtracao` |
| `AlphaVantageClient` (`extracao/alpha_vantage.py`) | monta a URL, faz o HTTP, interpreta o JSON e classifica erros |
| `EtapaExtracao` (`extracao/extrator.py`) | pede os dados à `FonteDados` e aplica o modo incremental |
| `EtapaTransformacao` | deduplica, imputa, valida, marca outliers e escala o volume |
| `EtapaCarga` | upsert no SQLite (`dados/cotacoes.db`) |
| `EtapaModelagem` / `EtapaVisualizacao` | modelos, métricas, gráficos e CSV |
| `Pipeline` (`nucleo/etapa.py`) | encadeia as etapas e mede o tempo de cada uma |

### Problemas de design a demonstrar

Cada problema precisa ser **mostrado na execução** e **apontado no código**.
Os números de linha abaixo são do `main` atual; conferir antes de gravar.

| # | Problema | Onde está | Consequência / como demonstrar |
|---|---|---|---|
| P1 | **Custo sem controle:** toda execução faz uma requisição por símbolo. Não há cache. | `extrator.py:246` chama a fonte sempre; `alpha_vantage.py:153-157` (`_requisitar`) vai sempre à rede | O free tier dá 25 chamadas/dia. Rodar `main.py` duas vezes mostra `chamadas_reais` subindo de novo. Desenvolver ou depurar queima a cota. |
| P2 | **Sem retry:** o cliente classifica `ErroTransitorio`, mas **ninguém repete**. | `alpha_vantage.py:158-162` lança o erro; `extrator.py:246` não trata; `config.py:271` (`PoliticaRetry`) é **código morto**, nunca usado | Um erro de limite por segundo ou de rede derruba o pipeline inteiro. Demonstrar com a fonte forçando um erro transitório. |
| P3 | **Chave não validada antes da rede:** a chave vazia ou mal formada só falha depois de gastar uma chamada. | `config.py:302` aceita `""`; o erro só aparece em `alpha_vantage.py:177-180` | Um erro de configuração custa uma requisição real e a mensagem vem do servidor. |
| P4 | **Criação antecipada do objeto caro:** o cliente (com a sessão HTTP) é criado mesmo que nada vá para a rede. | `main.py:60` (`criar_fonte`); `alpha_vantage.py:136` | Custo **pequeno** neste caso (a `requests.Session` é barata). Apresentar com honestidade, como argumento fraco; só vira forte se a criação do objeto for pesada (o toy problem mostra isso melhor). |
| P5 | **Preocupações transversais não têm lugar certo:** cache, retry e validação têm de ir ou para o `AlphaVantageClient` (que hoje só fala HTTP) ou para `EtapaExtracao` (que hoje só orquestra). | `alpha_vantage.py` e `extrator.py` | Qualquer das duas escolhas mistura responsabilidades e obriga a editar uma classe que já funciona (evolução/extensão). |
| P6 | **Vazamento do tipo concreto:** o `main` precisa saber que a fonte é um `AlphaVantageClient` para mostrar `chamadas_reais`. | `main.py:77` (`isinstance(fonte, AlphaVantageClient)`) | Qualquer decorador ou substituto da fonte some dessa saída. É um sinal de acoplamento ao concreto. |

**Pré-condição já satisfeita (não é um defeito):** `FonteDados` é uma interface e
`EtapaExtracao` só depende dela. O Proxy exige que o substituto tenha a mesma
interface do objeto real; por isso o código original **precisa** manter isso.

### Por que o Proxy é pertinente (para argumentar na gravação)

P1 a P3 são justamente as razões clássicas do Proxy, e todas aparecem aqui:
**custo** (cache), **acesso/proteção** (validar a chave) e **falha de recurso remoto**
(retry). Todas pedem um "intermediário" com a mesma interface, para o cliente
(`EtapaExtracao`) não precisar mudar.

### Pendências da Parte 1

- [ ] Escrever o roteiro em `docs/parte1_problema_original.md`, com os problemas P1-P6 e as
      linhas conferidas.
- [ ] Preparar um comando de demo que mostre P1 (rodar 2× e comparar `chamadas_reais`),
      P2 (erro transitório derrubando o pipeline) e P3 (chave vazia).
- [ ] **Manter** no `main` os comentários que apontam onde o proxy entraria (docstring de
      `main.py:3-7`, docstring de `alpha_vantage.py:1-6`, comentário em
      `alpha_vantage.py:134-135`, docstring de `config.py:272`). Eles servem à Parte 1:
      o enunciado pede **localizar e explicar os trechos responsáveis pelos problemas**.
      Usá-los como âncoras na gravação, e conferir que cada um bate com um problema
      P1-P6 (e que dizem o *problema*, e não só "o proxy vai resolver").
- [ ] Limpar o `import` duplicado em `main.py:14-15` (descuido, sem relação com o padrão).
- [ ] Decidir se `PoliticaRetry` fica no `main` como código morto (e apontar isso como
      problema) ou se é movida para a branch `proxy-bom`.

---

## Parte 2 — Toy problem (`toy_problem/`)

> **Responsável: outra pessoa do grupo.** Esta seção é só referência para alinhar com
> ela; a nossa parte é a 3 (e o suporte à 1). Combinar a interface/nomes para a Parte 3
> retomar o mesmo vocabulário (Subject, RealSubject, Proxy).

Precisa ser **diferente** do pipeline e **simples** o bastante para ensinar o padrão.
Deve ter um `README` próprio e rodar sozinho (`python -m ...`) e com testes.

Sugestão: visualizador de imagens (ou documentos) pesados.
- `Imagem` (Subject): `exibir()`.
- `ImagemReal` (RealSubject): carrega o arquivo no construtor (custo alto, simulado
  com `time.sleep`).
- `ImagemProxy` (Proxy): cria a `ImagemReal` só na primeira exibição (**proxy virtual**)
  e, opcionalmente, confere a permissão antes (**proxy de proteção**).

O código deve permitir mostrar: os 3 papéis, o fluxo de chamada, a mesma
interface, vantagens (criação adiada, controle de acesso) e limitações (indireção,
latência extra na 1ª chamada, mais uma classe).

---

## Parte 3 — Refatoração com Proxy (`proxy-bom`)

Sai do `main` e acrescenta `extracao/proxy_fonte.py` com `FonteDadosProxy(FonteDados)`.

| Responsabilidade | Problema que resolve | O que faz |
|---|---|---|
| **Proteção** | P3 | chave vazia ou com formato inválido → `ErroAutenticacao` antes de qualquer chamada |
| **Cache** | P1 | guarda o `LoteExtracao` bruto em `dados/cache/`, chave `(simbolo, tamanho)`, validade (ex.: 12h). Hit → não chama a API |
| **Virtual (lazy)** | P4 | recebe uma *factory* do cliente real e só o cria no 1º cache miss |
| **Retry** | P2 | repete só `ErroTransitorio`, com `PoliticaRetry.espera(i)`; `ErroPermanente` sobe direto |

- Ligar por `USAR_PROXY=true` no `.env`, dentro de `criar_fonte()`.
- **Não deve mudar:** `EtapaExtracao`, `AlphaVantageClient`, `Pipeline`. Esse é o
  argumento central: o cliente da interface não percebe a troca.
- **P6:** o proxy precisa expor `chamadas_reais` (de alguma forma) para a demo não quebrar.
  Decidir e registrar a escolha (isso é um ponto para a discussão de design).
- Usar `LoteExtracao.to_dict()`/`from_dict()` para serializar o cache.

### Pronto quando

- Testes cobrem: 2ª chamada sai do cache; cache vencido chama de novo; cliente **não é
  criado** se tudo vier do cache; chave vazia é barrada; retry recupera de falha
  transitória; erro permanente não é repetido.
- **Comportamento preservado:** a saída do pipeline (DataFrames limpos e métricas) é a
  mesma com e sem proxy. Ter um teste comparando as duas.
- Demo rodando 2× com o proxy: a 1ª com `chamadas_reais=1`, a 2ª com `chamadas_reais=0`.

### O que preparar para a gravação (exigido pelo enunciado)

- **Papéis no código:** `FonteDados` = Subject, `AlphaVantageClient` = RealSubject,
  `FonteDadosProxy` = Proxy, `EtapaExtracao` = cliente.
- **Mapa problema → solução:** para cada P1-P6, o trecho do proxy que o trata.
- **Pontos de extensão:** ex.: novo proxy de *rate limit* (1 req/s), de *logging*,
  proxies empilhados (um proxy sobre outro, já que todos têm a mesma interface),
  ou uma nova `FonteDados` (outra API) reaproveitando o mesmo proxy.
- **"E se...":** e se o cache for removido? E se o proxy chamar o cliente real
  diretamente em vez de pela `FonteDados`? E se o retry for movido para o cliente?
  Justificar as dependências escolhidas.

---

## Parte 4 — Avaliação crítica

Deve ser fundamentada nas **duas implementações** (original × `proxy-bom`), com
dados medidos. Pontos que o código sustenta:

- **Benefícios obtidos:** `chamadas_reais` caiu de N para 0 na 2ª execução; erro de chave
  deixou de gastar cota; retry recupera falha transitória. Medir tempo (cache vs. rede).
- **Custos:** nova classe, cache em disco (invalidação, validade, chave), concorrência/
  arquivos corrompidos, mais configuração, mais caminhos para testar, indireção ao depurar.
- **Quando não usar:** quando não há custo, acesso ou latência a controlar. Exemplo local:
  a Transformação (ver abaixo).
- **Limitações:** o cache serve dado velho por até a validade (12h); o proxy não resolve o
  limite de 25/dia sozinho (só reduz); o P4 tem ganho pequeno aqui.

### Exemplo de mau uso (opcional): `proxy-ruim`

`EtapaTransformacao(escala_volume=...)` recebe uma `Escala` (`transformacao/escala.py`).
Branch `proxy-ruim` (sai do `main`) com `transformacao/proxy_escala.py` →
`EscalaProxy(Escala)`, que só repassa `transformar()` para uma `EscalaLog`.

- **Uso na apresentação:** **somente na Parte 4**, como contraste ("quando não usar").
  Não é refatoração: o enunciado pede melhoria, e este proxy não melhora nada.
- Mostrar: mesma saída (teste comparando DataFrames), mesmo tempo, e nenhuma das razões
  do Proxy (sem rede, sem cota, sem permissão, criar o objeto é trivial).
- Se o objetivo fosse trocar a técnica de escala, o padrão certo já está ali: **Strategy**
  (`Escala` com `EscalaLog`/`EscalaMinMax`).
- Se faltar tempo, é a primeira coisa a cortar.

---

## Branches

| Branch | Conteúdo |
|---|---|
| `main` | Pipeline **sem proxy**: é o "problema original" (Parte 1). |
| `proxy-bom` | `main` + `FonteDadosProxy` na Extração: é a refatoração (Parte 3). |
| `proxy-ruim` | (opcional) `main` + `EscalaProxy`: só para a Parte 4. |

- **Não colocar código de proxy no `main`.**
- Quando o `main` mudar, atualizar as demais com `git merge main`.

---

## Como o código está organizado

```
ES_proxy/
├── main.py                       # monta o pipeline e escolhe a FonteDados (criar_fonte) e a Escala
├── docs/enunciado.pdf            # enunciado do trabalho
├── src/pipeline_proxy/
│   ├── config.py                 # Config + PoliticaRetry
│   ├── dominio.py                # schema OHLCV, LoteExtracao, enums
│   ├── erros.py                  # ErroTransitorio / ErroPermanente e subclasses
│   ├── nucleo/etapa.py           # contrato Etapa + Pipeline (mede tempo por etapa)
│   ├── extracao/                 # fonte.py (Subject), alpha_vantage.py (RealSubject), estado.py, extrator.py
│   ├── transformacao/            # limpeza.py, escala.py, etapa.py
│   ├── carga/etapa.py            # SQLite, upsert
│   ├── modelagem/etapa.py        # random walk × SMA, MAE/RMSE
│   └── visualizacao/etapa.py     # PNG/HTML + CSV
├── dados/                        # gerado em runtime (no .gitignore)
└── tests/                        # fakes.py (FonteFake) + testes por etapa
```

### Contratos importantes

- **Etapa:** `nome` e `executar(entrada) -> saida`; o `Pipeline` encadeia a saída de uma
  na entrada da próxima.
- **Dados brutos:** a Extração devolve `list[LoteExtracao]`; cada lote tem um DataFrame
  `simbolo, data, open, high, low, close, volume`. A Extração **não limpa nada**.
- **Dados limpos:** a Transformação devolve **um** `pd.DataFrame` (colunas
  `COLUNAS_LIMPAS`: brutas + `valida`, `retorno`, `outlier`, `volume_escalado`). Duplicadas
  são removidas; inválidas e outliers são só **marcados**.
- **Erros:** `ErroTransitorio` (inclui `ErroLimiteRequisicoes`) = vale repetir;
  `ErroPermanente` (inclui `ErroAutenticacao`, `ErroCotaEsgotada`) = não vale. A Alpha
  Vantage responde HTTP 200 mesmo em erro; a mensagem vem no corpo.

### Convenções

- Nomes de classes, funções e variáveis em **português**.
- Interfaces como `ABC`; dependências recebidas no construtor.
- Testes **nunca** acessam a internet: usar `tests/fakes.py` e `tests/fixtures/`
  (HTTP mockado com `responses`).
- Logs com prefixo curto (`[API] ...`) para a demo ficar legível.
- Commits no formato `tipo(escopo): descrição` (`feat`, `test`, `docs`, `chore`).

### Fatos da Alpha Vantage

- Free tier: 25 requisições/dia, burst de 1 requisição/segundo.
- `outputsize=full` e `TIME_SERIES_DAILY_ADJUSTED` são **premium**; o gratuito dá os
  ~100 últimos pregões (`compact`).
- A chave `demo` só aceita a URL exata da documentação e só funciona com `IBM`.
- Ações da B3 usam o sufixo `.SAO` (`PETR4.SAO`), não `.SA`.
