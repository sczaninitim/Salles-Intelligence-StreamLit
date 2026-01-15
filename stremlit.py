import streamlit as st
import pandas as pd
from pytrends.request import TrendReq
from pytrends.exceptions import TooManyRequestsError
import plotly.express as px
import plotly.graph_objects as go
import time, random

# =========================
# Configuração inicial
# =========================
st.set_page_config(page_title="Google Trends Dashboard", layout="wide")

# Detectar tema do Streamlit para ajustar cores
is_light_theme = (st.get_option("theme.base") == "light")
if is_light_theme:
    header_note_color = "black"
    font_color = "black"
    bg_color = "white"
    line_color_table = 'rgba(0,0,0,0.1)'
    grid_color = 'rgba(0,0,0,0.1)'
    line_color_plot = 'rgba(0,0,0,0.15)'
    paper_bgcolor = 'white'
    plot_bgcolor = 'white'
else:
    header_note_color = "gray"
    font_color = "rgb(230,230,230)"
    bg_color = 'rgba(0,0,0,0)'
    line_color_table = 'rgba(255,255,255,0.15)'
    grid_color = 'rgba(200,200,200,0.2)'
    line_color_plot = 'rgba(255,255,255,0.15)'
    paper_bgcolor = 'rgba(0,0,0,0)'
    plot_bgcolor = 'rgba(0,0,0,0)'

# =========================
# Cabeçalho com LOGO clicável + TÍTULO
# =========================
TIM_LOGO_URL = "https://logos-world.net/wp-content/uploads/2021/03/TIM-Emblem.png"
TIM_LINK = "https://www.tim.com.br/rj"

header_html = f"""
<style>
.header-flex {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 4px;
}}
.header-flex img {{
    height: 44px;
    object-fit: contain;
    display: inline-block;
    cursor: pointer;
}}
.header-flex h1 {{
    margin: 0;
    padding: 0;
}}
.subheader-note {{
    font-size: 14px;
    /* Usando variável de cor do tema do Streamlit para texto secundário */
    color: var(--secondary-text-color);
    margin-top: 4px;
}}
</style>

<div class="header-flex">
    <a href="{TIM_LINK}" target="_blank">
        <img src="{TIM_LOGO_URL}" alt="TIM Logo">
    </a>
    <h1>Google Trends Dashboard</h1>
</div>

<div class="subheader-note">
    Análise de buscas no Google Trends – Brasil (Total)
</div>
"""
st.markdown(header_html, unsafe_allow_html=True)

# =========================
# Inicialização do estado
# =========================
defaults = {
    'terms': [], 
    'timeframe': "today 12-m",
    'geo': "BR",            
    'resolution': "REGION", 
    'interest_over_time': None,
    'interest_by_region': None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =========================
# Pytrends client
# =========================
pytrends = TrendReq(hl='pt-BR', tz=360)

# =========================
# Funções com retry/backoff
# =========================
def with_backoff(call_fn, max_retries=6, base_delay=2.0, label=""):
    for attempt in range(max_retries):
        try:
            return call_fn()
        except TooManyRequestsError:
            wait = base_delay * (2 ** attempt) + random.uniform(0, base_delay)
            st.warning(
                f"Limite atingido pelo Google (429) {label}. "
                f"Tentativa {attempt+1}/{max_retries}. Aguardando {wait:.1f}s…"
            )
            time.sleep(wait)
    return call_fn()

@st.cache_data(ttl=1800, show_spinner=True)
def get_trends_data(terms, timeframe, geo, resolution):
    def _build():
        pytrends.build_payload(terms, cat=0, timeframe=timeframe, geo=geo, gprop='')
        return True
    with_backoff(_build, label="(payload)")
    time.sleep(1.0)
    interest_over_time = with_backoff(pytrends.interest_over_time, label="(time series)")
    time.sleep(1.0)
    def _ibr():
        return pytrends.interest_by_region(resolution=resolution, inc_low_vol=True, inc_geo_code=False)
    interest_by_region = with_backoff(_ibr, label=f"(by {resolution.lower()})")
    time.sleep(0.8)
    return interest_over_time, interest_by_region

# =========================
# Sidebar
# =========================
st.sidebar.header("Configurações")
terms_input = st.sidebar.text_input("Digite os termos separados por vírgula", "tim, claro")
period_options = ["today 12-m", "today 3-m", "today 1-m", "today 5-y", "now 7-d", "now 1-H"]
timeframe_option = st.sidebar.selectbox("Período", period_options)

st.sidebar.caption("Área geográfica: Brasil (Total) – visão por estado (REGION)")
st.sidebar.divider()

# Opções de suavização
smooth_lines = st.sidebar.checkbox("Suavizar linhas (média móvel + spline)", value=True)

def default_smoothing_window(tf):
    if tf in ("now 1-H", "now 7-d"):
        return 24
    elif tf in ("today 1-m", "today 3-m", "today 12-m"):
        return 7
    elif tf == "today 5-y":
        return 30
    return 7

win_default = default_smoothing_window(timeframe_option)
if smooth_lines:
    win_size = st.sidebar.slider("Janela média móvel", min_value=3, max_value=60, value=win_default, step=1)
else:
    win_size = None

st.sidebar.divider()
use_interactive_table = st.sidebar.toggle("Tabela interativa (Plotly Table com rolagem)", value=True)

# =========================
# Botão de busca
# =========================
if st.sidebar.button("Buscar Dados"):
    st.session_state['terms'] = [t.strip() for t in terms_input.split(",") if t.strip()]
    st.session_state['timeframe'] = timeframe_option
    st.session_state['geo'] = "BR"
    st.session_state['resolution'] = "REGION"
    with st.spinner("Carregando dados do Google Trends…"):
        iot, ibr = get_trends_data(
            st.session_state['terms'],
            st.session_state['timeframe'],
            st.session_state['geo'],
            st.session_state['resolution']
        )
    st.session_state['interest_over_time'] = iot
    st.session_state['interest_by_region'] = ibr

# =========================
# Área principal
# =========================
if st.session_state['interest_over_time'] is not None:
    terms = st.session_state['terms']
    interest_over_time = st.session_state['interest_over_time']
    interest_by_region = st.session_state['interest_by_region'].reset_index()

    if "isPartial" not in interest_over_time.columns:
        interest_over_time["isPartial"] = False

    start_date = pd.to_datetime(interest_over_time.index.min()).date() if not interest_over_time.empty else None
    end_date = pd.to_datetime(interest_over_time.index.max()).date() if not interest_over_time.empty else None

    interest_by_region['Período'] = st.session_state['timeframe']
    interest_by_region['Inicio'] = start_date
    interest_by_region['Fim'] = end_date

    # 1) Série temporal
    with st.container(border=True):
        st.subheader("Evolução das buscas")
        terms_for_plot = [t for t in interest_over_time.columns if t != 'isPartial']

        plot_df = interest_over_time.reset_index()
        if smooth_lines and len(terms_for_plot) > 0 and win_size:
            smoothed = plot_df[terms_for_plot].rolling(window=win_size, min_periods=1).mean()
            plot_df = pd.concat([plot_df[['date']], smoothed], axis=1)

        fig_time = px.line(
            plot_df, x='date', y=terms_for_plot,
            title=f"Interesse ao longo do tempo – Período: {st.session_state['timeframe']}"
        )
        fig_time.update_traces(line_shape='spline')
        fig_time.update_layout(
            hovermode="x unified",
            xaxis=dict(showgrid=True, gridcolor=grid_color, showline=True, linecolor=line_color_plot),
            yaxis=dict(showgrid=True, gridcolor=grid_color, showline=True, linecolor=line_color_plot),
            margin=dict(t=60, l=40, r=20, b=40),
            paper_bgcolor=paper_bgcolor,
            plot_bgcolor=plot_bgcolor
        )
        st.plotly_chart(fig_time, use_container_width=True)

    st.divider()

    # 2) Ranking consolidado — tabela com altura ajustada e cores adaptativas ao tema
    cols = ['Período', 'Inicio', 'Fim', 'geoName'] + [t for t in terms if t in interest_by_region.columns]
    ranking_df = interest_by_region[cols].sort_values(by=terms, ascending=False)
    
    with st.container(border=True):
        st.subheader(
            f"Ranking por {st.session_state['resolution'].lower()} – Período: {st.session_state['timeframe']} "
            f"(de {start_date} até {end_date})"
        )
    
        if use_interactive_table:
            sort_cols = ['geoName'] + [t for t in terms if t in ranking_df.columns]
            sort_by = st.selectbox("Ordenar por:", sort_cols, index=0)
            sort_asc = st.toggle("Ordem crescente", value=False)
            ranking_sorted = ranking_df.sort_values(by=sort_by, ascending=sort_asc)
    
            header_values = list(ranking_sorted.columns)
            cell_values = [ranking_sorted[col].astype(str).tolist() for col in header_values]
    
            fig_table = go.Figure(data=[
                go.Table(
                    header=dict(
                        values=header_values,
                        fill_color=bg_color,
                        align="center",
                        font=dict(color=font_color, size=12),
                        height=32,
                        line_color=line_color_table
                    ),
                    cells=dict(
                        values=cell_values,
                        align="center",
                        fill_color=bg_color,
                        font=dict(color=font_color, size=12),
                        height=28,
                        line_color=line_color_table
                    )
                )
            ])
            table_height = 32 + 28 * len(ranking_sorted) + 20
            fig_table.update_layout(
                height=table_height,
                margin=dict(t=10, l=10, r=10, b=10),
                paper_bgcolor=bg_color,
                plot_bgcolor=bg_color
            )
            st.plotly_chart(fig_table, use_container_width=True)
    
        else:
            styler = (
                ranking_df
                .style
                .set_properties(**{
                    "text-align": "center",
                    "color": font_color,
                    "background-color": "transparent"
                })
                .set_table_styles([
                    {"selector": "th", "props": [("text-align", "center"), ("color", font_color), ("background-color", "transparent")]}
                ])
            )
            st.table(styler)

    # 3) Top 27
    with st.container(border=True):
        st.subheader(f"Top 27 Localizações – Termos: {terms} – Período: {st.session_state['timeframe']}")
        selected_term = st.selectbox(
            "Escolha o termo para o Top 27 e ranking:",
            terms, index=0
        )
        top_rank = ranking_df.head(27)
        fig_cities = px.bar(
            top_rank,
            x='geoName', y=selected_term,
            title=f"Top 27 ({st.session_state['timeframe']}) – {selected_term}",
            text=selected_term
        )
        fig_cities.update_traces(textposition='outside')
        fig_cities.update_layout(
            xaxis_title="Local",
            yaxis_title="Interesse",
            xaxis=dict(showgrid=False, showline=True, linecolor=line_color_plot),
            yaxis=dict(showgrid=True, gridcolor=grid_color),
            paper_bgcolor=paper_bgcolor,
            plot_bgcolor=plot_bgcolor
        )
        st.plotly_chart(fig_cities, use_container_width=True)

    st.divider()

    # 4) Comparativo entre termos
    with st.container(border=True):
        st.subheader("Comparação entre termos")
        fig_compare = go.Figure()
        for term in [t for t in interest_over_time.columns if t != 'isPartial']:
            fig_compare.add_trace(go.Box(y=interest_over_time[term], name=term))
        fig_compare.update_layout(
            boxmode='group',
            xaxis=dict(showgrid=False, showline=True, linecolor=line_color_plot),
            yaxis=dict(showgrid=True, gridcolor=grid_color),
            paper_bgcolor=paper_bgcolor,
            plot_bgcolor=plot_bgcolor
        )
        st.plotly_chart(fig_compare, use_container_width=True)

    st.divider()

    # 5) Exportação CSV normalizado
    with st.container(border=True):
        st.subheader("Exportação")
        df_csv = interest_over_time.reset_index()

        term_cols = [c for c in df_csv.columns if c not in ['date', 'isPartial']]
        df_csv_normalized = df_csv.copy()
        df_csv_normalized[term_cols] = (
            df_csv[term_cols].div(df_csv[term_cols].sum(axis=1), axis=0) * 100
        ).round(0).astype(int)

        cols_order = ['date'] + term_cols + ['isPartial']
        csv_data = df_csv_normalized[cols_order].to_csv(index=False)

        st.download_button(
            "Baixar série temporal (CSV)",
            csv_data,
            "trends_time_series_normalized_int.csv"
        )
else:
    st.info("Digite os termos e clique em **Buscar Dados** para iniciar a análise.")
