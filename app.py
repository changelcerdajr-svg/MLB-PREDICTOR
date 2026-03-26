# app.py
# MLB Quant Engine - Web Interface V12.3
import streamlit as st
import datetime
from market_scraper import get_live_market_odds
from model import MLBPredictor
from financial import american_to_prob, remove_vig, calculate_edge

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MLB Quant Engine", page_icon="⚾", layout="wide")

# --- CACHÉ DEL MODELO ---
@st.cache_resource
def load_predictor():
    return MLBPredictor()

st.title("🏛️ MLB Quant Engine V12.3")
st.markdown("**Core Estocástico:** NegBinomial (VMR=1.8 Empírico) | **Riesgo:** Kelly Fraccionario")
st.divider()

predictor = load_predictor()

# --- SELECTOR DE FECHA (NUEVO) ---
st.sidebar.header("📅 Control de Tiempo")
today = datetime.date.today()

# Permite navegar 7 días al pasado y 7 días al futuro
selected_date = st.sidebar.date_input(
    "Selecciona la fecha de operación:",
    today,
    min_value=today - datetime.timedelta(days=7),
    max_value=today + datetime.timedelta(days=7)
)
date_str = selected_date.strftime("%Y-%m-%d")

# --- CARGA DE JUEGOS ---
with st.spinner(f'Extrayendo calendario y variables para {date_str}...'):
    try:
        # Usamos el loader directo para inyectarle la fecha que elegimos
        games = predictor.loader.get_schedule(date_str)
    except Exception as e:
        st.error(f"Error de conexión con MLB API: {e}")
        games = []

if not games:
    st.warning(f"No hay juegos programados para el {date_str}.")
else:
    # --- BARRA LATERAL (SIDEBAR) ---
    st.sidebar.header("Pizarra de Juegos")
    
    game_options = {f"{g['away_name']} @ {g['home_name']}": g for g in games}
    selected_game_str = st.sidebar.selectbox("Selecciona un juego para auditar:", list(game_options.keys()))
    selected_game = game_options[selected_game_str]
    
    st.sidebar.divider()
    st.sidebar.info("Nota: Los juegos del futuro sin lineups confirmados bloquearán la predicción por seguridad, pero mostrarán el análisis base.")

    # --- MOTOR PREDICTIVO (PANEL CENTRAL) ---
    st.subheader(f"🏟️ Análisis: {selected_game['away_name']} vs {selected_game['home_name']}")
    
    with st.spinner('Corriendo simulaciones Monte Carlo y Stress Test...'):
        res = predictor.predict_game(selected_game)
        
    # Compuertas de Seguridad
    if 'error' in res:
        st.error("🛑 ALERTA DE RIESGO SISTÉMICO")
        st.write(res['error'])
        st.write("*Operación bloqueada por el motor para proteger el capital ante datos inestables.*")
    else:
        # Layout de 3 columnas para métricas principales
        col1, col2, col3 = st.columns(3)
        
        home_prob = res['home_prob'] * 100
        away_prob = res['away_prob'] * 100
        
        col1.metric("Ganador Proyectado", res['winner'].upper())
        col2.metric(f"Prob. {selected_game['home_name']}", f"{home_prob:.1f}%")
        col3.metric(f"Prob. {selected_game['away_name']}", f"{away_prob:.1f}%")
        
        st.markdown(f"**Factor Clave:** `{res['key_factor']}` | **Sensibilidad de Inputs:** `{res['details']['sensitivity']}`")
        st.markdown(f"**Carreraje Esperado:** {res['score']['away']:.1f} - {res['score']['home']:.1f}")
        
        # --- MÓDULO FINANCIERO (LIVE ODDS) ---
        st.markdown("---")
        st.markdown("### 💰 Parámetros Financieros (Live Odds)")
        
        live_odds = get_live_market_odds()
        home_key = selected_game['home_name'].lower()
        
        default_home = -110
        default_away = -110
        
        if home_key in live_odds:
            default_home = live_odds[home_key]['home_ml']
            default_away = live_odds[home_key]['away_ml']
            st.success("✅ Líneas de mercado sincronizadas en tiempo real desde Las Vegas (ESPN).")
        else:
            st.warning("⚠️ Líneas en vivo no detectadas para este juego. Ingresa manual.")
            
        col_fin1, col_fin2, col_fin3 = st.columns(3)
        
        with col_fin1:
            home_odds = st.number_input(f"Momio {selected_game['home_name']}", value=default_home, step=5)
        with col_fin2:
            away_odds = st.number_input(f"Momio {selected_game['away_name']}", value=default_away, step=5)
            
        with col_fin3:
            st.write("") 
            st.write("")
            calculate_btn = st.button("Calcular Valor Esperado (EV)", use_container_width=True)
            
        # --- VEREDICTO ---
        if calculate_btn and home_odds != 0 and away_odds != 0:
            raw_home = american_to_prob(home_odds)
            raw_away = american_to_prob(away_odds)
            mkt_home, mkt_away = remove_vig(raw_home, raw_away)
            
            if res['winner'] == selected_game['home_name']:
                analysis = calculate_edge(res['home_prob'], mkt_home)
                mkt_display = mkt_home * 100
            else:
                analysis = calculate_edge(res['away_prob'], mkt_away)
                mkt_display = mkt_away * 100
                
            st.markdown("#### 📊 Veredicto Cuantitativo")
            
            if analysis['kelly'] > 0:
                st.success(f"**{analysis['verdict']}** - Se detectó ineficiencia en el mercado.")
                
                res_col1, res_col2, res_col3 = st.columns(3)
                res_col1.metric("Prob. Mercado Límpia", f"{mkt_display:.1f}%")
                res_col2.metric("Edge Matemático", analysis['edge_pct'])
                res_col3.metric("Stake Recomendado", f"{analysis['kelly']*100:.2f}%")
                
                st.info(f"**Acción:** Invierte el {analysis['kelly']*100:.2f}% de tu Bankroll a favor de **{res['winner']}**.")
            else:
                st.error(f"**{analysis['verdict']}** - El mercado es eficiente en esta línea.")
                st.write(f"Probabilidad de Mercado ({mkt_display:.1f}%) > Probabilidad del Modelo ({max(home_prob, away_prob):.1f}%).")
                st.warning("🚫 Se prohíbe la inversión de capital en este evento.")