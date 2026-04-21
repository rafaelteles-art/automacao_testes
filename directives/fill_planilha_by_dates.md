# Preencher Planilha por Datas (Campanhas RedTrack)

## Objetivo
Cada planilha do Google Sheets é associada a uma ou mais campanhas do RedTrack. Em cada planilha, as colunas que tiverem **uma data na primeira linha** são preenchidas com a soma das métricas dessas campanhas para aquela data.

## Camadas

### Configuração (uma vez por planilha)
Arquivo: `config/planilhas.json` (gerenciado pelo módulo [planilha_config_store.py](../execution/planilha_config_store.py)).

Cada entrada contém:
- `id` — uuid gerado automaticamente
- `nome` — apelido livre
- `g_url` — link do Google Sheets
- `aba` — nome da aba
- `campaign_ids` — lista de IDs de campanhas RedTrack associadas
- `metric_rows` — dicionário `{ "linha": "métrica" }`. Ex.: `{"2": "cost", "3": "convtype2"}` significa "linha 2 recebe `cost`, linha 3 recebe `convtype2`". Esse mapeamento é **opcional** no cadastro mas **obrigatório** para que o preenchimento escreve algo.

### Execução
Script: [fill_planilha_by_dates.py](../execution/fill_planilha_by_dates.py)

Funções principais:
- `detect_date_columns(header_row)` — detecta colunas-data na linha 1 (aceita `DD/MM/YYYY`, `YYYY-MM-DD`, datetime, e serial Excel).
- `aggregate_metrics_by_date(rt_api, campaign_ids, date_start, date_end)` — chama `/report?group=date&campaign=<id>` para cada campanha e soma as métricas por dia.
- `build_preview(config, rt_token, gc)` — leitura + agregação, **não escreve**. Use para conferir dados antes.
- `fill_sheet(config, rt_token, gc)` — aplica `metric_rows` em todas as colunas-data detectadas.

### UI (Streamlit, [web_app.py](../execution/web_app.py))
Seção `📅 Preencher por Campanhas RedTrack`, com duas abas:
1. **Configurar Planilhas** — CRUD das planilhas e associação com campanhas RedTrack.
2. **Preencher Planilha** — escolha a planilha, gere preview ou execute o preenchimento.

## Métricas suportadas
Definidas em `SUPPORTED_METRICS` em [fill_planilha_by_dates.py](../execution/fill_planilha_by_dates.py): `cost`, `revenue`, `total_revenue`, `profit`, `roas`, `cpa`, `cpc`, `clicks`, `impressions`, `approved`, `convtype1..5`. Adicione ali se precisar de mais.

## Observações
- O escopo gspread atual é só `spreadsheets`; certifique-se de que o e-mail do robô (do `credentials.json`) tem permissão de **Editor** na planilha.
- O range de datas enviado ao RedTrack é o mínimo→máximo das datas detectadas na linha 1, em uma única chamada por campanha.
- O cache de campanhas RedTrack na UI é de 10 minutos (`fetch_rt_campaigns`).

## A definir (orientação futura do usuário)
- Como exatamente o `metric_rows` será usado em cada planilha real (quais linhas, quais métricas).
- Se haverá conversão de moeda (cost vem em USD).
- Se algumas linhas precisam de fórmulas em vez de valores numéricos.
