# Preencher Planilha por Datas (Campanhas RedTrack + A/B test VTurb)

## Objetivo
Cada planilha do Google Sheets é associada a:
- **Uma ou mais campanhas RedTrack** (tráfego/conversões), e
- **Um A/B test VTurb** (= 1 ou mais player_ids; métricas somadas entre variantes).

Em cada planilha, as colunas que tiverem **uma data na primeira linha** são preenchidas com a soma das métricas dessas campanhas/players para aquela data.

## Camadas

### Persistência (Google Sheets, multi-usuário)
Em produção (Streamlit Cloud) o filesystem é efêmero — JSONs em `config/` são apagados a cada reinício. Por isso, a fonte de verdade canônica é uma **planilha de config no Google Sheets**, com duas abas:

- **`planilhas`** — gerenciada por [planilha_config_store.py](../execution/planilha_config_store.py)
  - 1 linha por planilha. Colunas: `id | nome | g_url | aba | campaign_ids | metric_rows | vturb_player_ids`
  - `campaign_ids` / `vturb_player_ids`: separados por vírgula
  - `metric_rows`: JSON-encoded (deprecado — mantido só por retrocompat)
- **`labels`** — gerenciada por [label_map_store.py](../execution/label_map_store.py)
  - 1 linha por entrada. Colunas: `label | metric` (label já normalizado em uppercase, sem acento)

**Por que 1 linha por entrada:** `upsert` e `delete` operam num único range, então duas pessoas adicionando planilhas/labels ao mesmo tempo **não colidem** (cada `append_row` é atômico no lado do Google Sheets). A única colisão possível é dois usuários editando a mesma entrada no mesmo segundo, o que é desprezível com 2 usuários.

**Setup (uma vez):**
1. Crie uma Google Sheet vazia (vai armazenar as configs — não confundir com as planilhas-alvo de preenchimento).
2. Compartilhe com o `client_email` da service account (do `credentials.json`) como **Editor**.
3. Em **Streamlit Cloud → App settings → Secrets**, adicione:
   ```toml
   planilhas_config_sheet_url = "https://docs.google.com/spreadsheets/d/.../edit"
   ```
   Para dev local: defina a env var `PLANILHAS_CONFIG_SHEET_URL` no `.env`.
4. Os stores criam as abas `planilhas` e `labels` automaticamente no primeiro acesso. Se houver `config/planilhas.json` ou `config/metric_labels.json` locais e a aba estiver vazia, os dados locais são copiados (seed).

**Cache:** Cada store tem cache em memória com TTL de 30s para reduzir reads. Toda escrita invalida o cache local (mas não o cache do *outro* processo — janela máxima de divergência entre usuários é 30s).

**Fallback:** Se `planilhas_config_sheet_url` não estiver configurado, os stores caem no JSON local em `config/` (modo dev). A UI exibe um warning vermelho neste caso.

### Cadastro (uma vez por planilha)
Cada entrada contém:
- `id` — uuid gerado automaticamente
- `nome` — apelido livre
- `g_url` — link do Google Sheets-alvo
- `aba` — nome da aba
- `campaign_ids` — lista de IDs de campanhas RedTrack associadas
- `vturb_player_ids` — lista de player_ids VTurb que compõem o A/B test (métricas somadas entre os variantes)
- `metric_rows` — **deprecado**. O mapeamento linha→métrica agora é global (aba `labels`).

### Dicionário global Label → Métrica
Aba `labels` da planilha de config (ou `config/metric_labels.json` no fallback local).

Estrutura: `{ "labels": { "GASTO FACEBOOK": "cost", "CLIQUES": "clicks", ... } }`.

Chaves são normalizadas (uppercase + sem acentos + espaços colapsados) antes de gravar e antes de comparar com a coluna A. Isso faz com que "Visualização Página", "VISUALIZACAO PAGINA" e "  visualizacao pagina  " sejam a mesma entrada.

No preenchimento, o sistema lê a **coluna A** de cada planilha, normaliza cada célula, procura no dicionário e descobre qual métrica escrever em qual linha. Linhas sem correspondência no dicionário são silenciosamente ignoradas (linhas de fórmula, lucros calculados, etc).

### Execução
Scripts: [fill_planilha_by_dates.py](../execution/fill_planilha_by_dates.py) + cliente VTurb [vturb_api.py](../execution/vturb_api.py).

Funções principais:
- `detect_date_columns(header_row)` — detecta colunas-data na linha 1 (aceita `DD/MM/YYYY`, `YYYY-MM-DD`, datetime, e serial Excel).
- `label_map_store.resolve_rows(col_a_values)` — lê a coluna A e devolve `{linha: métrica}` baseado no dicionário global.
- `aggregate_metrics_by_date(rt_api, campaign_ids, date_start, date_end, vturb_api=None, vturb_player_ids=None)` — chama `/report?group=date&campaign=<id>` (RedTrack) para cada campanha e `/sessions/stats_by_day?player_id=<id>` (VTurb) para cada player; soma todas as métricas por dia.
- `build_preview(config, rt_token, gc, vturb_token=None)` — leitura + agregação + resolução de linhas via coluna A, **não escreve**. Use para conferir dados antes. Retorno inclui `resolved_rows`.
- `fill_sheet(config, rt_token, gc, vturb_token=None)` — aplica `resolved_rows` (vindo do label map global) em todas as colunas-data detectadas.

**Ratios VTurb (multi-player):** `vturb_play_rate`, `vturb_over_pitch_rate` são **recomputados** a partir dos totais somados (numerador/denominador) em vez de média direta dos valores da API. `vturb_engagement_rate` é média ponderada por `total_viewed`.

### UI (Streamlit, [web_app.py](../execution/web_app.py))
Seção `📅 Preencher por Campanhas RedTrack`, com duas abas:
1. **Configurar Planilhas** — CRUD das planilhas e associação com campanhas RedTrack + players VTurb (A/B test).
2. **Preencher Planilha** — escolha a planilha, gere preview ou execute o preenchimento.

A sidebar do Streamlit aceita **três tokens**: Facebook Ads, RedTrack e VTurb.

## Métricas suportadas
Definidas em `SUPPORTED_METRICS` em [fill_planilha_by_dates.py](../execution/fill_planilha_by_dates.py):

**RedTrack (campanhas):** `cost`, `revenue`, `total_revenue`, `profit`, `roas`, `cpa`, `cpc`, `clicks`, `impressions`, `approved`, `convtype1..40`, `revenuetype1..40`, etc.

**VTurb (A/B test):** `vturb_viewed`, `vturb_viewed_session_uniq`, `vturb_viewed_device_uniq`, `vturb_started`, `vturb_started_session_uniq`, `vturb_started_device_uniq`, `vturb_finished`, `vturb_clicked`, `vturb_over_pitch`, `vturb_under_pitch`, `vturb_play_rate`, `vturb_over_pitch_rate`, `vturb_engagement_rate`. Mapeamento nome→raw em `VTURB_METRIC_FIELDS` em [vturb_api.py](../execution/vturb_api.py).

Adicione em `SUPPORTED_METRICS` / `VTURB_METRIC_FIELDS` se precisar de mais.

## Observações
- O escopo gspread atual é só `spreadsheets`; certifique-se de que o e-mail do robô (do `credentials.json`) tem permissão de **Editor** na planilha.
- O range de datas enviado ao RedTrack é o mínimo→máximo das datas detectadas na linha 1, em uma única chamada por campanha.
- O cache de campanhas RedTrack e players VTurb na UI é de 10 minutos (`fetch_rt_campaigns`, `fetch_vturb_players`).
- **VTurb API**: base `https://analytics.vturb.net`, headers `X-Api-Token` + `X-Api-Version: v1`. Datas precisam vir como `YYYY-MM-DD HH:MM:SS` (o `VTurbAPI` padroniza internamente).
- **VTurb A/B test**: não tem endpoint nativo. Um A/B test é só um conjunto de `player_id`s; no cadastro, o usuário seleciona os variantes manualmente e as métricas são somadas.

## A definir (orientação futura do usuário)
- Como exatamente o `metric_rows` será usado em cada planilha real (quais linhas, quais métricas).
- Se haverá conversão de moeda (cost vem em USD).
- Se algumas linhas precisam de fórmulas em vez de valores numéricos.
