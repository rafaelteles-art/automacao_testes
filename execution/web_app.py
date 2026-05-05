import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sys
import os
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Adicionar o diretório de execução ao path para importar a API do Facebook e Excel Utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from facebook_redtrack_importer_v2 import FacebookAdsAPI, ExcelManager, main as run_importer_script
from fill_creative_tests import fill_creative_tests

# Configuração da página Streamlit
st.set_page_config(page_title="Gestor de Performance FB Ads", page_icon="📈", layout="wide")

# Sidebar - Configurações Iniciais
st.sidebar.title("Configurações ⚙️")

# Default token (ocultado do código fonte no production)
st.sidebar.markdown("**Tokens de Integração API**")
fb_token = st.sidebar.text_input("Token do Facebook Ads", type="password")

if not fb_token:
    fb_token = "EAAWDHozjODgBRYSLNrJKwCXTvowH12ayUGzsp7bZBqbHZBGFrQcaZAXpFwgiq3byQ2cg6ZBHFZCLn8hCXZAN8ZB1BzjQZBbtEP8jgdGzcpdNiFfgXZCKtTzNVQZAAYclfzwEyLOfsL3eazEIe22X5PQnJ6qUSZCn266p1Oi0eEQ84yFMh7tvg6SblkNFlMgZAxlwXDji"

rt_token = st.sidebar.text_input("Chave de API RedTrack", type="password")

if not rt_token:
    rt_token = "wB7qY69R0KVU9tl4TBaQ"

vturb_token = st.sidebar.text_input("Chave de API VTurb", type="password")

if not vturb_token:
    vturb_token = "62a36884887710e04f6ee66cde9ee9cebeef8efe6c50f25aa07437cb0111e0d6"

st.sidebar.markdown("---")

@st.cache_resource
def get_fb_api(token):
    return FacebookAdsAPI(token)

# Título Principal do App
st.title("Gestor de Performance - Criativos 🚀")
st.markdown("Filtre e visualize a performance das suas campanhas em tempo real diretamente da API do Facebook Ads e RedTrack.")

# Área de parâmetros do filtro
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 1. Data do Relatório")
    date_start = st.date_input("Data Inicial", datetime.now() - timedelta(days=30))
    date_end = st.date_input("Data Final", datetime.now())

with col2:
    st.markdown("### 2. Conta de Anúncios")
    
    # Vamos armazenar cache de instâncias API para performance
    fb_api = get_fb_api(fb_token)
    
    @st.cache_data(ttl=3600, show_spinner=False)
    def fetch_bms(token):
        bms = get_fb_api(token).get_business_managers()
        return bms if bms else None # Retorna None se falhar em vez de [] vazio para evitar cache infinito

    col_bm_refresh = st.columns([3, 1])
    with col_bm_refresh[1]:
        if st.button("🔄", help="Recarregar lista de BMs"):
            fetch_bms.clear()
            st.rerun()

    bm_list = fetch_bms(fb_token)

    if bm_list is not None:
        st.caption(f"{len(bm_list)} BM(s) encontrado(s)")

    if bm_list is None:
         st.error("Token do Facebook inválido ou expirado. Cole um novo token no menu lateral.")
         bm_options = {}
    else:
         bm_options = {f"{bm['name']} ({bm['id']})": bm['id'] for bm in bm_list}
         
    if not bm_options:
        st.selectbox("Selecione o(s) Business Manager(s)", ["Nenhum encontrado"])
        selected_bm_names = []
    else:
        default_bm = list(bm_options.keys())  # Select ALL BMs by default so no account is missed
        selected_bm_names = st.multiselect("Selecione o(s) Business Manager(s)", list(bm_options.keys()), default=default_bm)
    
    selected_bm_ids = [bm_options.get(name) for name in selected_bm_names]
    selected_account_names = []
    selected_account_ids = []

    @st.cache_data(ttl=3600)
    def fetch_accounts(token, bm_id):
         return get_fb_api(token).get_ad_accounts(bm_id)

    if selected_bm_ids:
        with st.spinner('Carregando Ad Accounts...'):
            account_list = []
            for bm_id in selected_bm_ids:
                accounts = fetch_accounts(fb_token, bm_id)
                if accounts:
                    account_list.extend(accounts)
                    
            if account_list:
                account_options = {f"{acc['name']} ({acc['id']})": acc['id'] for acc in account_list}
                default_val = list(account_options.keys())  # Select ALL accounts by default
                selected_account_names = st.multiselect("Selecione a(s) Conta(s) de Anúncios", list(account_options.keys()), default=default_val)
                selected_account_ids = [account_options.get(name) for name in selected_account_names]
            else:
                st.warning("Nenhuma conta de anúncios encontrada. Verifique se os BMs possuem contas ativas.")

with col3:
    st.markdown("### 3. Filtrar Campanha")
    campaign_filter = st.text_input("Filtrar por nome de Campanha", placeholder="Nome ou termo (ex. CBO-01)")
    
    st.markdown("### 4. Nível dos Dados")
    report_level_name = st.radio(
        "Velocidade vs Detalhe:",
        ["Campanha (Mais rápido, evita quedas)", "Anúncio (Completo, mais lento)"]
    )
    report_level = "campaign" if "Campanha" in report_level_name else "ad"

# Adicionar função de dashboard
def render_dashboard(df, filter_text):
    if df.empty:
        st.warning("Sem dados para exibir o Dashboard.")
        return

    # Clean numeric types
    numeric_cols = ['impressions', 'clicks', 'spend', 'cpm', 'ctr', 'cpc']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Filtrar localmente caso haja filtro
    if filter_text:
        # Tenta achar qual coluna é o nome da campanha no dataframe
        search_col = 'campaign_name' if 'campaign_name' in df.columns else None
        
        # Fallback de busca se não tiver 'campaign_name' explícito, procura em qualquer outra coluna txt
        if not search_col and 'ad_name' in df.columns:
             search_col = 'ad_name'
             
        if search_col:
            import re
            # Permite pesquisar mais de um termo separando por vírgulas (ex: "CBO, LAL")
            terms = [re.escape(t.strip()) for t in str(filter_text).replace(';', ',').split(',') if t.strip()]
            if terms:
                pattern = '|'.join(terms)
                st.info(f"Filtro aplicado (Regex Pattern): `{pattern}` na coluna `{search_col}`")
                df[search_col] = df[search_col].astype(str)
                df = df[df[search_col].str.contains(pattern, case=False, na=False, regex=True)]
        else:
             st.warning("Aviso: A API retornou dados sem a coluna de nome da campanha para filtragem.")
             
    if df.empty:
         st.warning("Nenhum dado sobrou após aplicar o filtro de Campanha de CBO.")
         return

    label_col = 'ad_name' if 'ad_name' in df.columns else 'campaign_name'
    if label_col not in df.columns:
        label_col = df.columns[0]
        
    # Agrupar se o df for muito grande e houver a coluna campaign_name
    if len(df) > 30 and 'campaign_name' in df.columns:
        df = df.groupby('campaign_name').sum(numeric_only=True).reset_index()
        label_col = 'campaign_name'
        
    fig = make_subplots(
        rows=2, cols=2, 
        subplot_titles=("Spend Overview", "CPM by Ad", "CTR Performance", "Impressions vs Clicks")
    )

    if 'spend' in df.columns:
        fig.add_trace(go.Bar(x=df[label_col], y=df['spend'], name="Spend"), row=1, col=1)

    if 'cpm' in df.columns:
        fig.add_trace(go.Bar(x=df[label_col], y=df['cpm'], name="CPM", marker_color='orange'), row=1, col=2)

    if 'ctr' in df.columns:
        fig.add_trace(go.Bar(x=df[label_col], y=df['ctr'], name="CTR", marker_color='green'), row=2, col=1)

    if 'impressions' in df.columns and 'clicks' in df.columns:
        fig.add_trace(go.Scatter(x=df['impressions'], y=df['clicks'], mode='markers', text=df[label_col], name="Imp vs Clicks", marker=dict(size=10, color='red')), row=2, col=2)

    fig.update_layout(
        height=700,
        showlegend=False,
        template="plotly_dark"
    )

    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, use_container_width=True)

st.markdown("---")

# Botão principal de ação
if st.button("🚀 Importar & Gerar Dashboard", type="primary"):
    if not selected_account_ids:
        st.error("É necessário selecionar ao menos uma Conta de Anúncios para iniciar!")
    else:
        with st.status("Processando dados de API...", expanded=True) as status:
            st.write("Conectando no Facebook Ads API...")
            
            progress_text = st.empty()
            
            def update_progress(info):
                if isinstance(info, int):
                    progress_text.write(f"📥 Baixando páginas... {info} anúncios coletados até agora.")
                else:
                    progress_text.error(str(info))
            
            all_fb_data = []
            for acc_id in selected_account_ids:
                progress_text.write(f"🔍 Coletando dados da conta: {acc_id}")
                padded_date_end = date_end + timedelta(days=1)
                fb_data = fb_api.get_ad_insights(
                    acc_id, 
                    date_start.strftime('%Y-%m-%d'), 
                    padded_date_end.strftime('%Y-%m-%d'),
                    level=report_level,
                    progress_callback=update_progress
                )
                if fb_data:
                    for item in fb_data:
                        item['account_id'] = acc_id
                    all_fb_data.extend(fb_data)
            
            if not all_fb_data:
                 status.update(label="Falha na Importação ou Nenhuma Campanha no Período", state="error", expanded=True)
                 st.error("Nenhum dado retornado. Verifique se o Token expirou ou se de fato não há anúncios ativos neste mês para as contas selecionadas.")
            else:
                 st.write("Carregando Dados...")
                 status.update(label="Dados extraídos com Sucesso!", state="complete", expanded=False)
            
        if all_fb_data:
            st.success(f"Foram encontrados {len(all_fb_data)} anúncios somando {len(selected_account_ids)} conta(s)!")
            
            # Transform data into pandas DF for Dashboard plotting
            df = pd.DataFrame(all_fb_data)
            
            with st.expander("🛠️ Debug: Ver Tabela de Dados Brutos da API (Antes do Filtro)"):
                st.dataframe(df)

            st.markdown("## 📊 Dashboard de Performance")
            render_dashboard(df, campaign_filter)

st.markdown("---")
st.markdown("## 📝 Preencher Planilha (Google Sheets)")
st.markdown("Insira o Link da sua Planilha do Google e selecione a Aba.")

import gspread
from google.oauth2.service_account import Credentials
import json

@st.cache_resource
def get_gspread_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    try:
        has_secret = False
        try:
            has_secret = "gcp_service_account" in st.secrets
        except Exception:
            has_secret = False
        if has_secret:
            # Load from secrets (assuming it's a dict or JSON string)
            secret_info = st.secrets["gcp_service_account"]
            if isinstance(secret_info, str):
                secret_info = json.loads(secret_info)
            else:
                # Convert explicitly to a dict (st.secrets returns a SecretDict object, but from_service_account expects standard dict)
                secret_info = dict(secret_info)
                
            creds = Credentials.from_service_account_info(secret_info, scopes=scopes)
            return gspread.authorize(creds)
        elif os.path.exists("credentials.json"):
            creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
            return gspread.authorize(creds)
    except Exception as e:
        import traceback
        st.error(f"Erro ao carregar credenciais: {e} | {traceback.format_exc()}")
    return None

gc = get_gspread_client()

if gc is None:
    st.warning("⚠️ **Autenticação Pendente:** Para acessar o Google Sheets, você precisa configurar um arquivo `credentials.json` na raiz do projeto ou no Streamlit Secrets em `[gcp_service_account]`.")
    st.stop()

# Connection UI
g_url = st.text_input("🔗 Link da Planilha do Google (ex: https://docs.google.com/spreadsheets/d/...)")

if g_url:
    try:
        # Load the spreadsheet
        with st.spinner("Conectando ao Google Sheets..."):
            sh = gc.open_by_url(g_url)
            worksheets = sh.worksheets()
            sheet_names = [ws.title for ws in worksheets]
        
        selected_sheet = st.selectbox("📋 Selecione a Aba para preencher", sheet_names)
        
        if st.button("✍️ Iniciar Preenchimento na Nuvem", type="primary"):
            from fill_creative_tests import fill_creative_tests
            
            if not selected_account_ids:
                st.error("Selecione uma ou mais Contas de Anúncios antes de iniciar.")
            else:
                with st.status("Preenchendo planilha online...", expanded=True) as fill_status:
                    fill_progress = st.empty()

                    def fill_progress_cb(msg):
                        fill_progress.write(f"⏳ {msg}")

                    try:
                        padded_date_end = date_end + timedelta(days=1)
                        result = fill_creative_tests(
                            account_ids=selected_account_ids,
                            date_start=date_start.strftime('%Y-%m-%d'),
                            date_end=padded_date_end.strftime('%Y-%m-%d'),
                            g_url=g_url,
                            sheet_name=selected_sheet,
                            fb_token=fb_token,
                            redtrack_token=rt_token,
                            progress_callback=fill_progress_cb,
                            gc=gc # Pass the authenticated client
                        )
                        fill_status.update(label="Planilha do Google atualizada com sucesso! ✅", state="complete", expanded=False)
                    except gspread.exceptions.APIError as e:
                        fill_status.update(label="Erro de Permissão no Google Sheets", state="error", expanded=True)
                        st.error(f"❌ O Google recusou a alteração. A planilha está compartilhada com o e-mail do robô (`client_email` do credentials.json) como Editor? Erro: {e}")
                        result = None
                    except Exception as e:
                        fill_status.update(label="Erro ao preencher planilha", state="error", expanded=True)
                        import traceback
                        st.error(f"❌ Erro fatal: {e} | {traceback.format_exc()}")
                        result = None
                        
                if result:
                    pe_msg = f"\n\n📈 PRÉ-ESCALA: {result.get('filled_pre_escala', 0)} criativos preenchidos (Gasto, Vendas, ROAS, CPA)." if result.get('filled_pre_escala', 0) > 0 else ""
                    st.success(f"✅ Sucesso! A aba '{selected_sheet}' foi atualizada ao vivo.\nForam preenchidos {result['filled_metrics']} Testes Completos.\n\n📊 {result['filled_a']} novas marcações na Coluna A.\n⏭️ {result['skipped_rows']} linhas foram puladas.{pe_msg}")
                    
                    if result['not_found']:
                        with st.expander(f"⚠️ {len(result['not_found'])} Anúncios não encontrados nas campanhas:"):
                            st.write("Verifique se o nome inserido na planilha existe no final do nome de alguma campanha ativa desta conta:")
                            st.write("`, `".join(result['not_found']))
    except Exception as e:
        st.error(f"❌ Não foi possível acessar a planilha. Verifique o link ou se o e-mail do robô foi adicionado como Editor no Google Sheets! ({e})")

# =============================================================================
# Preencher por Campanhas RedTrack (datas no cabeçalho → soma das campanhas)
# =============================================================================
st.markdown("---")
st.markdown("## 📅 Preencher por Campanhas RedTrack")
st.caption("Cada planilha é associada a uma ou mais campanhas. As colunas que tiverem uma data na primeira linha são preenchidas com a soma das métricas dessas campanhas para aquela data.")

import planilha_config_store as cfg_store
import label_map_store
from facebook_redtrack_importer_v2 import RedTrackAPI
from vturb_api import VTurbAPI
from fill_planilha_by_dates import (
    SUPPORTED_METRICS,
    build_preview,
    fill_sheet,
)

# Persistent storage for planilhas + label dictionary.
# In Streamlit Cloud the local filesystem is ephemeral, so JSON files in
# `config/` are wiped on every restart. Configure a Google Sheet to be the
# durable source of truth — set `planilhas_config_sheet_url` in st.secrets
# (or the env var PLANILHAS_CONFIG_SHEET_URL for local dev).
def _get_config_sheet_url():
    try:
        url = st.secrets.get("planilhas_config_sheet_url")
        if url:
            return str(url)
    except Exception:
        pass
    return os.environ.get("PLANILHAS_CONFIG_SHEET_URL") or None

_config_sheet_url = _get_config_sheet_url()
if _config_sheet_url:
    cfg_store.configure(gc, _config_sheet_url)
    label_map_store.configure(gc, _config_sheet_url)
    st.caption(f"💾 Config persistente: planilha de config no Google Sheets.")
else:
    st.warning(
        "⚠️ **Persistência local apenas** — planilhas cadastradas e o dicionário de labels "
        "vão sumir a cada reinício do Streamlit Cloud. Configure uma planilha de config no "
        "Google Sheets e adicione `planilhas_config_sheet_url = \"https://docs.google.com/...\"` "
        "em **Settings → Secrets** (compartilhada com o e-mail do robô como Editor)."
    )

@st.cache_data(ttl=600, show_spinner=False)
def fetch_rt_campaigns(token):
    rt = RedTrackAPI(token)
    return rt.list_campaigns()


@st.cache_data(ttl=600, show_spinner=False)
def fetch_vturb_players(token):
    if not token:
        return []
    try:
        return VTurbAPI(token).list_players()
    except Exception:
        return []

tab_cfg, tab_run = st.tabs(["⚙️ Configurar Planilhas", "▶️ Preencher Planilha"])

with tab_cfg:
    st.markdown("### Planilhas cadastradas")

    rt_campaigns = fetch_rt_campaigns(rt_token) if rt_token else []
    if not rt_campaigns:
        st.warning("Não consegui listar campanhas do RedTrack. Verifique a chave de API no menu lateral.")
    else:
        st.caption(f"{len(rt_campaigns)} campanhas RedTrack disponíveis para associação.")
    campaign_label = {c["id"]: f"{c['title']} ({c['id']})" for c in rt_campaigns}
    label_to_id = {v: k for k, v in campaign_label.items()}

    vturb_players = fetch_vturb_players(vturb_token) if vturb_token else []
    if vturb_players:
        st.caption(f"{len(vturb_players)} players VTurb disponíveis para associação (A/B test = N players somados).")
    else:
        st.caption("Nenhum player VTurb disponível (verifique a chave de API VTurb no menu lateral).")
    vturb_label = {p["id"]: f"{p.get('name', p['id'])} ({p['id']})" for p in vturb_players}
    vturb_label_to_id = {v: k for k, v in vturb_label.items()}

    planilhas = cfg_store.load_all()
    if not planilhas:
        st.info("Nenhuma planilha cadastrada ainda. Use o formulário abaixo.")
    for p in planilhas:
        n_vturb = len(p.get("vturb_player_ids", []) or [])
        header = f"📄 {p['nome']}  —  aba: {p['aba']}  —  {len(p.get('campaign_ids', []))} campanha(s)"
        if n_vturb:
            header += f"  —  {n_vturb} player(s) VTurb"
        with st.expander(header):
            st.write(f"**URL:** {p['g_url']}")
            st.write("**Campanhas associadas:**")
            for cid in p.get("campaign_ids", []):
                st.write(f"- {campaign_label.get(cid, cid)}")
            if p.get("vturb_player_ids"):
                st.write("**Players VTurb (A/B test):**")
                for pid in p["vturb_player_ids"]:
                    st.write(f"- {vturb_label.get(pid, pid)}")
            st.caption("Linhas desta planilha serão resolvidas pela coluna A no momento do preenchimento (dicionário global abaixo).")

            col_e, col_d = st.columns([1, 1])
            with col_e:
                if st.button("✏️ Editar", key=f"edit_{p['id']}"):
                    st.session_state["editing_planilha_id"] = p["id"]
                    st.rerun()
            with col_d:
                if st.button("🗑️ Excluir", key=f"del_{p['id']}"):
                    cfg_store.delete(p["id"])
                    st.success("Planilha removida.")
                    st.rerun()

    st.markdown("---")
    editing_id = st.session_state.get("editing_planilha_id")
    editing = cfg_store.get(editing_id) if editing_id else None
    st.markdown("### " + ("Editar planilha" if editing else "Adicionar planilha"))

    with st.form("planilha_form", clear_on_submit=False):
        nome_v = st.text_input("Nome (apelido livre)", value=editing.get("nome") if editing else "")
        url_v = st.text_input("Link da Planilha do Google", value=editing.get("g_url") if editing else "")
        aba_v = st.text_input("Nome da aba", value=editing.get("aba") if editing else "")

        default_labels = []
        if editing:
            default_labels = [campaign_label[cid] for cid in editing.get("campaign_ids", []) if cid in campaign_label]
        camp_v = st.multiselect(
            "Campanhas RedTrack associadas",
            options=list(label_to_id.keys()),
            default=default_labels,
        )

        default_vturb_labels = []
        if editing:
            default_vturb_labels = [vturb_label[pid] for pid in editing.get("vturb_player_ids", []) if pid in vturb_label]
        vturb_v = st.multiselect(
            "Players VTurb (A/B test — métricas somadas entre variantes)",
            options=list(vturb_label_to_id.keys()),
            default=default_vturb_labels,
            help="Selecione 1 ou mais players. Para A/B test, marque todos os variantes — views, plays, pitch etc. serão somados.",
        )

        st.caption("ℹ️ O preenchimento agora identifica a linha pelo valor da **coluna A** (ex. 'GASTO FACEBOOK'). Edite o dicionário global abaixo para controlar label → métrica.")

        col_s, col_c = st.columns([1, 1])
        with col_s:
            submitted = st.form_submit_button("💾 Salvar", type="primary")
        with col_c:
            cancelled = st.form_submit_button("Cancelar")

        if cancelled and editing_id:
            del st.session_state["editing_planilha_id"]
            st.rerun()

        if submitted:
            if not nome_v or not url_v or not aba_v:
                st.error("Nome, link e aba são obrigatórios.")
            else:
                cfg_store.upsert(
                    nome=nome_v,
                    g_url=url_v,
                    aba=aba_v,
                    campaign_ids=[label_to_id[lbl] for lbl in camp_v],
                    metric_rows=editing.get("metric_rows") if editing else {},
                    planilha_id=editing_id,
                    vturb_player_ids=[vturb_label_to_id[lbl] for lbl in vturb_v],
                )
                if editing_id:
                    del st.session_state["editing_planilha_id"]
                st.success("Planilha salva.")
                st.rerun()

    st.markdown("---")
    st.markdown("### 🗂️ Dicionário global Label → Métrica")
    st.caption(
        "Mapeia o texto da **coluna A** de cada planilha → métrica que deve ir naquela linha. "
        "Normalização: maiúsculas, sem acento, espaços colapsados. Vale para todas as planilhas."
    )

    labels_map = label_map_store.load()
    col_label_tbl, col_label_edit = st.columns([2, 1])

    with col_label_tbl:
        if labels_map:
            st.dataframe(
                pd.DataFrame(
                    [{"Label (col. A normalizada)": k, "Métrica": v} for k, v in sorted(labels_map.items())]
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Dicionário vazio. Adicione entradas ao lado.")

    with col_label_edit:
        with st.form("label_map_form", clear_on_submit=True):
            new_label = st.text_input("Label (como aparece na coluna A)", placeholder="GASTO FACEBOOK")
            new_metric = st.selectbox(
                "Métrica",
                options=[""] + sorted(SUPPORTED_METRICS),
                help="Métricas RedTrack + VTurb disponíveis.",
            )
            add_btn = st.form_submit_button("➕ Adicionar / Atualizar", type="primary")
            if add_btn and new_label and new_metric:
                label_map_store.upsert_one(new_label, new_metric)
                st.success(f"Salvo: `{label_map_store.normalize_label(new_label)}` → `{new_metric}`")
                st.rerun()

        if labels_map:
            to_remove = st.selectbox(
                "Remover entrada",
                options=[""] + sorted(labels_map.keys()),
                key="label_map_remove",
            )
            if st.button("🗑️ Remover", disabled=not to_remove):
                label_map_store.delete_one(to_remove)
                st.success(f"Removido: `{to_remove}`")
                st.rerun()

with tab_run:
    planilhas = cfg_store.load_all()
    if not planilhas:
        st.info("Cadastre uma planilha primeiro na aba **Configurar Planilhas**.")
    else:
        nome_to_id = {f"{p['nome']} — {p['aba']}": p["id"] for p in planilhas}
        chosen_label = st.selectbox("Planilha", list(nome_to_id.keys()))
        chosen_id = nome_to_id[chosen_label]
        chosen = cfg_store.get(chosen_id)

        st.write(
            f"**Campanhas:** {len(chosen.get('campaign_ids', []))}  |  "
            f"**Players VTurb:** {len(chosen.get('vturb_player_ids', []) or [])}  |  "
            f"**Aba:** `{chosen['aba']}`"
        )
        st.markdown("**Filtrar range de datas** (processa só colunas cuja data da linha 1 cair no intervalo)")
        use_range = st.checkbox("Aplicar filtro de datas", value=False, key="use_date_range")
        filter_start = filter_end = None
        if use_range:
            col_ds, col_de = st.columns([1, 1])
            with col_ds:
                filter_start = st.date_input("Data inicial", datetime.now().date() - timedelta(days=7), key="range_start")
            with col_de:
                filter_end = st.date_input("Data final", datetime.now().date(), key="range_end")
            if filter_start and filter_end and filter_start > filter_end:
                st.error("A data inicial deve ser menor ou igual à final.")

        col_p, col_f = st.columns([1, 1])
        run_preview = col_p.button("🔎 Pré-visualizar (sem gravar)")
        run_fill = col_f.button("✍️ Preencher na planilha", type="primary")

        if run_preview or run_fill:
            with st.status("Processando...", expanded=True) as s:
                progress_box = st.empty()
                def _cb(msg):
                    progress_box.write(f"⏳ {msg}")
                try:
                    if run_fill:
                        result = fill_sheet(
                            chosen, rt_token, gc, progress=_cb,
                            filter_start=filter_start, filter_end=filter_end,
                            vturb_token=vturb_token,
                        )
                        s.update(label="Preenchimento concluído ✅", state="complete", expanded=False)
                    else:
                        preview = build_preview(
                            chosen, rt_token, gc, progress=_cb,
                            filter_start=filter_start, filter_end=filter_end,
                            vturb_token=vturb_token,
                        )
                        result = {"updates": 0, "preview": preview, "skipped_dates": [], "note": "preview only"}
                        s.update(label="Preview gerado ✅", state="complete", expanded=False)
                except Exception as e:
                    import traceback
                    s.update(label="Erro", state="error", expanded=True)
                    st.error(f"❌ {e}\n\n{traceback.format_exc()}")
                    result = None

            if result:
                preview = result["preview"]
                date_cols = preview["date_columns"]
                if not date_cols:
                    st.warning("Nenhuma data foi detectada na linha 1 da aba selecionada.")
                else:
                    st.success(f"{len(date_cols)} coluna(s) de data detectada(s) entre {preview['range'][0]} e {preview['range'][1]}.")
                    resolved = preview.get("resolved_rows") or {}
                    if resolved:
                        st.caption(
                            f"🧩 {len(resolved)} linha(s) resolvida(s) via coluna A: "
                            + ", ".join(f"L{r}→{m}" for r, m in sorted(resolved.items()))
                        )
                    else:
                        st.warning("Nenhuma linha bateu com o dicionário global. Edite o dicionário na aba **Configurar Planilhas**.")
                    if result.get("updates"):
                        st.info(f"✅ {result['updates']} célula(s) gravada(s).")
                    if result.get("skipped_dates"):
                        st.caption(f"Datas sem dados no RedTrack: {', '.join(result['skipped_dates'])}")

                    rows_data = []
                    for col_idx, day in date_cols:
                        bucket = preview["totals_by_date"].get(day, {})
                        rows_data.append({"col": col_idx, "data": day, **{m: bucket.get(m, 0) for m in SUPPORTED_METRICS}})
                    st.dataframe(pd.DataFrame(rows_data), use_container_width=True)
