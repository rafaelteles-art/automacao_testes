---
description: Preencher Coluna TC da planilha criativa usando dados da API do Facebook
---

# Preencher Planilha - Teste de Criativos

## Objetivo
Preencher a **Coluna A** (`TC`) da aba `032026` no arquivo `FB - LOTTO V7.xlsx` com o identificador
do teste de criativo e o nome da conta (ex: `TC238 CA6.DIANA`), baseando-se nos nomes de anúncios
que o usuário inseriu manualmente na **Coluna B**.

## Inputs

| Parâmetro | Origem | Exemplo |
|---|---|---|
| account_id | Seleção do usuário no app | `act_123456789` |
| date_start | Seleção do usuário | `2026-02-01` |
| date_end | Seleção do usuário | `2026-03-03` |
| fb_token | Campo do painel lateral ou default hardcoded | `EAAW...` |

## Script de Execução

`execution/fill_creative_tests.py`

### Fluxo

1. Chama `FacebookAdsAPI.get_ad_insights()` com `level='ad'` para obter `campaign_name` + `ad_name` de todos os anúncios da conta no período.
2. Constrói um índice `{ad_name_lower → campaign_name}`.
3. Para cada linha da aba `032026` com valor na Coluna B (nome do anúncio):
   - Busca no índice qual `campaign_name` contém o nome do anúncio (filtro "contém", case-insensitive).
   - Extrai `TCxxx` usando regex `TC(\d+)`.
   - Extrai o nome da conta usando o padrão `]CONTA TC`.
   - Escreve `TCxxx CONTA` na Coluna A.
4. Mescla as células consecutivas da Coluna A que têm o mesmo valor (mesmo TC).
5. Salva o arquivo Excel.

## Formato do Nome de Campanha

```
[LOTTOV7]CA6.DIANA TC238 ABO 1-50-1 - LT801.30
            ↑            ↑                ↑
         Conta          TC             Anúncio
```

**Coluna A resultante:** `TC238 CA6.DIANA`

## Execução via CLI

```bash
python execution/fill_creative_tests.py \
  --account-id act_123456 \
  --date-start 2026-02-01 \
  --date-end 2026-03-03
```

## Execução via Web App

1. Selecionar a BM e a Conta de Anúncios no painel.
2. Definir o período de datas.
3. Preencher a **Coluna B** do Excel com os nomes dos anúncios.
4. Clicar em **"✍️ Preencher Coluna TC"** na seção "Preencher Planilha" da página.

## Colunas de Métricas (seção TESTES)

Preenchidas apenas quando a Coluna M contém `TESTE`:

| Coluna | Métrica | Fonte |
|---|---|---|
| E / F | Hook Rate / Body75 | Facebook insights |
| G / H / I | CPM / CTR / CPC | Facebook insights |
| J | Gasto | RedTrack (`cost`) |
| K | Vendas | RedTrack (`convtype2`) |
| L | CPA | Calculado (gasto / vendas) |
| N | Initiate Checkout (IC) | RedTrack (`convtype1`) |

> O mapeamento `convtype1` = IC vem de `label_map_store.py` (`"IC": "convtype1"`).

## Notas e Edge Cases

- **O código do teste (BM188, BM108.1, ...) fica no NOME DO ANÚNCIO, não no nome da campanha.** O match da linha usa `match_ads` sobre um índice `{ad_name → [{ad_id, campaign_id, campaign_name}]}` (nome exato → boundary no termo → termo base). O índice por nome de campanha (`extract_ad_name_from_campaign`) fica só como fallback para anúncios antigos cujo código aparecia no nome da campanha. Já foi um bug: indexar só campanhas fazia ~81 de 96 anúncios (ex: BM188–BM261) caírem em "não encontrados" e não serem preenchidos. Coberto por `execution/test_ad_name_matching.py`.
- **NUNCA catalogar via `/act_X/ads` (catálogo completo) — usar insights por conta.** As contas têm 300k+ anúncios acumulados; paginar o catálogo levava uma eternidade. O fluxo rápido: ler a planilha PRIMEIRO, coletar os períodos distintos (data da Col C → data fim) das linhas TESTE, e fazer UMA varredura `/act_X/insights?level=ad` por período (`fetch_fb_ad_insights_for_accounts`). Insights só retornam anúncios que ENTREGARAM no período (centenas, não 300k), e a mesma varredura serve de índice de nomes (`build_ad_index`) E de fonte de métricas por linha — zero chamadas FB por linha. Tradeoff conhecido: anúncio sem entrega no período não aparece no índice (Col A não preenche pra ele), o que é aceitável pois também não teria métrica.
- **Janelas grandes em contas grandes estouram o limite de dados do FB** (erro code 1, status 500: "Please reduce the amount of data you're asking for"). A varredura degrada automaticamente (`_fetch_account_insights_adaptive`): 1º reduz o `limit` da página (250→50); se ainda recusar, divide o período ao meio recursivamente e mescla os resultados por anúncio com `merge_insight_rows`, que reconstrói as taxas a partir dos componentes brutos (clicks = ctr×imps, videos = hook×imps, p75 = body×imps) — matematicamente idêntico a uma varredura única. Coberto por `test_ad_name_matching.py`.
- **RedTrack é cacheado por período (`fetch_rt_report` + `_rt_report_cache`).** ~100 linhas compartilham poucos períodos distintos; o relatório completo (agrupado por `rt_ad` ou `sub4`) é puxado uma vez por período e filtrado localmente por linha. Só pulls completos entram no cache (falha transitória não envenena as demais linhas). O antigo "glitch retry" (re-fetch após 3s) foi removido — com o relatório completo em cache ele não fazia sentido.
- **RedTrack é desacoplado do match do Facebook.** Gasto/Vendas/IC/CPA e o veredito (VALIDADO/DESCARTADO) são preenchidos para qualquer anúncio com dados no RedTrack, mesmo sem campanha FB correspondente. As colunas só-do-FB (Hook/Body/CPM/CTR/CPC) e o rótulo da Coluna A é que dependem do match do FB. Antes, `if not matched_infos: continue` descartava a linha inteira antes de consultar o RedTrack.
- **A linha do cabeçalho é detectada dinamicamente** (Col A == `TC` e Col B == `CRIATIVO`); os dados começam na linha seguinte. O `DATA_START_ROW=4` fixo pulava a 1ª linha de dados em abas cujo cabeçalho está na linha 2 (ex: `DADOS_TESTE`).
- **A data inicial vem da PLANILHA, não do painel.** `derive_auto_date_start` varre as linhas em TESTE (Col C na seção TESTES, Col P na PRÉ-ESCALA) e usa o "Início" mais antigo como data inicial. Linhas sem data usam essa data derivada; o `date_start` escolhido no painel só entra como último recurso quando nenhuma linha em TESTE tem data. Isso evita que um teste antigo ainda aberto (ex: BDM de abril) seja cortado por uma data tardia escolhida na UI.
- **Variações do mesmo anúncio (ex: BM108.1 / BM108.2 / BM108.3) devem ter métricas do Facebook diferentes.** As métricas do FB (Hook, Body75, CPM, CTR, CPC) DEVEM ser puxadas em `level='ad'` e casadas pelo `ad_name` exato da variação (`fetch_fb_ad_insights_for_campaign` + `select_ad_metrics`). Já foi um bug: puxar em `level='campaign'` retornava o agregado da campanha, então todas as variações que compartilham a mesma campanha eram preenchidas idênticas (só o Gasto/Vendas do RedTrack, que casa por `rt_ad` exato, variava). Regressão coberta por `execution/test_variation_metrics.py`.
- Se um anúncio não for encontrado na API, a Coluna A fica em branco e o nome do anúncio aparece no aviso de "Não encontrados".
- Se o Excel estiver aberto no Excel ao rodar o script, ele vai falhar ao salvar. Feche o arquivo antes.
- O período de datas deve cobrir quando os anúncios estiveram ativos.
