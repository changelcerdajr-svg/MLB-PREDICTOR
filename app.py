# app.py
# MLB Quant Engine - Web Interface V14.1 (Navegación de Fecha Mejorada)

import streamlit as st
import datetime
from market_scraper import get_live_market_odds
from model import MLBPredictor
from financial import american_to_prob, remove_vig, calculate_edge

st.set_page_config(page_title="MLB Quant Engine", page_icon="⚾", layout="wide")

@st.cache_resource
def load_predictor():
    return MLBPredictor()

st.title("🏛️ MLB Quant Engine V14.1")
st.markdown("**Core Estocástico:** NegBinomial (VMR=1.8) | **Riesgo:** Kelly Fraccionario")
st.divider()

predictor = load_predictor()

# --- SELECTOR DE FECHA CON FLECHAS ---
st.sidebar.header("📅 Control de Tiempo")

# Inicializar la fecha en la memoria de la sesión
if 'op_date' not in st.session_state:
    st.session_state.op_date = datetime.date.today()

# Funciones para los botones de avanzar y retroceder
def prev_day():
    st.session_state.op_date -= datetime.timedelta(days=1)

def next_day():
    st.session_state.op_date += datetime.timedelta(days=1)

# Acomodamos: [Boton Atrás] [Calendario] [Boton Adelante]
col1, col2, col3 = st.sidebar.columns([1, 3, 1])

with col1:
    st.button("◀", on_click=prev_day, use_container_width=True)
with col2:
    # Mantenemos el calendario por si quieres saltar varios días, pero sin título para ahorrar espacio
    st.date_input("Fecha", key='op_date', label_visibility="collapsed")
with col3:
    st.button("▶", on_click=next_day, use_container_width=True)

date_str = st.session_state.op_date.strftime("%Y-%m-%d")

# Extraer momios del scraper
live_odds = get_live_market_odds()

# --- CARGA DE JUEGOS ---
with st.spinner(f'Extrayendo pizarra de {date_str}...'):
    try:
        games = predictor.loader.get_schedule(date_str)
    except Exception as e:
        st.error(f"Error de conexión con MLB API: {e}")
        games = []

if not games:
    st.warning(f"No hay juegos programados para el {date_str}.")
else:
    # --- UI: TARJETAS EN LA BARRA LATERAL ---
    st.sidebar.header("Pizarra de Juegos")
    
    # Resetear el juego seleccionado si cambiamos de día
    if 'selected_game_id' not in st.session_state or st.session_state.get('last_date') != date_str:
        st.session_state.selected_game_id = games[0]['id']
        st.session_state.last_date = date_str

    for g in games:
        status_raw = g.get('status', '')
        if status_raw in ['Live', 'In Progress']:
            status_ui = "🔴 EN VIVO"
        elif status_raw in ['Final', 'Game Over', 'Completed', 'F']:
            status_ui = "✅ FINAL"
        else:
            status_ui = "🕒 PROGRAMADO"

        # Caja para cada juego
        with st.sidebar.container():
            st.markdown(f"**{g['away_name']} @ {g['home_name']}**")
            st.caption(f"Estatus: {status_ui}")
            
            if st.button("📊 Analizar", key=f"btn_{g['id']}", use_container_width=True):
                st.session_state.selected_game_id = g['id']
            st.divider()

    # --- PANEL PRINCIPAL ---
    selected_game = next((g for g in games if g['id'] == st.session_state.selected_game_id), games[0])
    
    st.subheader(f"Análisis: {selected_game['away_name']} vs {selected_game['home_name']}")
    
    with st.spinner("Corriendo simulaciones de Monte Carlo..."):
        predictor.loader._force_historical_mode = False 
        res = predictor.predict_game(selected_game)

    if 'error' in res:
        st.error(f"🛑 OPERACIÓN BLOQUEADA: {res['error']}")
    else:
        away_team = selected_game['away_name']
        home_team = selected_game['home_name']
        away_runs = res['score']['away']
        home_runs = res['score']['home']
        
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            st.info("🎯 Probabilidades")
            st.write(f"**{away_team}:** {res['away_prob']*100:.1f}%")
            st.write(f"**{home_team}:** {res['home_prob']*100:.1f}%")
            
        with col_b:
            st.success("⚾ Carreraje Esperado")
            # ORDEN CORREGIDO: Visitante primero, luego Local
            st.markdown(f"#### {away_team} **{away_runs:.1f} - {home_runs:.1f}** {home_team}")
            st.caption(f"Total Proyectado: {res['score']['total']:.1f} carreras")
            
        with col_c:
            st.warning("⚠️ Diagnóstico de Riesgo")
            st.write(f"**Factor Clave:** {res['key_factor']}")
            st.write(f"**Sensibilidad:** {res['details']['sensitivity']}")

        st.divider()
        st.subheader("🏦 Mesa de Inversión (Line Shopping)")
        
        official_home = home_team.lower()
        game_odds = live_odds.get(official_home, None)
        
        if game_odds:
            st.success("✅ Líneas capturadas de The Odds API")
            home_ml = game_odds['home_ml']
            away_ml = game_odds['away_ml']
        else:
            st.warning("⚠️ Líneas no disponibles. Ingresa momios manuales (-110, +120):")
            c_m1, c_m2 = st.columns(2)
            # ORDEN CORREGIDO TAMBIÉN EN MOMIOS MANUALES
            away_ml = c_m1.number_input(f"Momio {away_team}", value=-110, step=5)
            home_ml = c_m2.number_input(f"Momio {home_team}", value=-110, step=5)
            
        p_home_market = american_to_prob(home_ml)
        p_away_market = american_to_prob(away_ml)
        p_home_clean, p_away_clean = remove_vig(p_home_market, p_away_market)
        
        if res['winner'] == home_team:
            calc = calculate_edge(res['home_prob'], p_home_clean)
            target_team = home_team
            target_ml = home_ml
        else:
            calc = calculate_edge(res['away_prob'], p_away_clean)
            target_team = away_team
            target_ml = away_ml
            
        st.markdown("### Veredicto del Sistema")
        v_col1, v_col2 = st.columns(2)
        
        with v_col1:
            st.metric("Ventaja Matemática (Edge)", calc['edge_pct'])
            st.write(f"**Recomendación:** {calc['verdict']}")
            
        with v_col2:
            kelly_pct = calc['kelly'] * 100
            st.metric("Gestión de Riesgo (1/4 Kelly)", f"{kelly_pct:.2f}% del Bankroll")
            if kelly_pct > 0:
                st.info(f"👉 Invertir **{kelly_pct:.2f}%** a favor de **{target_team}** (Cuota: {target_ml})")