# app.py
# MLB Quant Engine - Web Interface V14.0 (UI Institucional)

import streamlit as st
import datetime
from market_scraper import get_live_market_odds
from model import MLBPredictor
from financial import american_to_prob, remove_vig, calculate_edge

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MLB Quant Engine", page_icon="⚾", layout="wide")

@st.cache_resource
def load_predictor():
    return MLBPredictor()

st.title("🏛️ MLB Quant Engine V14.0")
st.markdown("**Core Estocástico:** NegBinomial (VMR=1.8) | **Riesgo:** Kelly Fraccionario")
st.divider()

predictor = load_predictor()

# --- SELECTOR DE FECHA ---
st.sidebar.header("📅 Control de Tiempo")
today = datetime.date.today()
selected_date = st.sidebar.date_input(
    "Fecha operativa:",
    today,
    min_value=today - datetime.timedelta(days=7),
    max_value=today + datetime.timedelta(days=7)
)
date_str = selected_date.strftime("%Y-%m-%d")

# Extraer momios del scraper (The Odds API)
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
    # --- NUEVA UI: TARJETAS EN LA BARRA LATERAL ---
    st.sidebar.header("Pizarra de Juegos")
    
    # Inicializar el estado de la sesión si no existe
    if 'selected_game_id' not in st.session_state:
        st.session_state.selected_game_id = games[0]['id']

    # Dibujar cada juego como una tarjeta independiente
    for g in games:
        # Lógica para detectar si está en vivo, terminado o por jugar
        status_raw = g.get('status', '')
        if status_raw in ['Live', 'In Progress']:
            status_ui = "🔴 EN VIVO"
        elif status_raw in ['Final', 'Game Over', 'Completed', 'F']:
            status_ui = "✅ FINALIZADO"
        else:
            status_ui = "🕒 PROGRAMADO"

        # Crear la caja visual en la barra lateral
        with st.sidebar.container():
            st.markdown(f"**{g['away_name']} @ {g['home_name']}**")
            st.caption(f"Estatus: {status_ui}")
            
            # El botón actualiza qué juego se muestra en el panel principal
            if st.button("📊 Analizar", key=f"btn_{g['id']}"):
                st.session_state.selected_game_id = g['id']
            st.divider() # Línea separadora entre juegos

    # --- PANEL PRINCIPAL DE ANÁLISIS ---
    # Encontrar los datos del juego que el usuario clickeó
    selected_game = next((g for g in games if g['id'] == st.session_state.selected_game_id), games[0])
    
    st.subheader(f"Análisis: {selected_game['away_name']} vs {selected_game['home_name']}")
    
    with st.spinner("Corriendo simulaciones de Monte Carlo..."):
        # Forzamos validación estricta (sin inyecciones)
        predictor.loader._force_historical_mode = False 
        res = predictor.predict_game(selected_game)

    if 'error' in res:
        st.error(f"🛑 OPERACIÓN BLOQUEADA: {res['error']}")
    else:
        # --- NUEVO FORMATO DE CARRERAJE (Visitante - Local) ---
        away_team = selected_game['away_name']
        home_team = selected_game['home_name']
        away_runs = res['score']['away']
        home_runs = res['score']['home']
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.info("🎯 Probabilidades Cuantitativas")
            st.write(f"**{away_team}:** {res['away_prob']*100:.1f}%")
            st.write(f"**{home_team}:** {res['home_prob']*100:.1f}%")
            
        with col2:
            st.success("⚾ Carreraje Esperado (Simulado)")
            # Aquí respetamos el orden visual que pediste
            st.markdown(f"#### {away_team} **{away_runs:.1f} - {home_runs:.1f}** {home_team}")
            st.caption(f"Total Proyectado: {res['score']['total']:.1f} carreras")
            
        with col3:
            st.warning("⚠️ Diagnóstico de Riesgo")
            st.write(f"**Factor Clave:** {res['key_factor']}")
            st.write(f"**Sensibilidad:** {res['details']['sensitivity']}")

        # --- MÓDULO FINANCIERO Y DE KELLY ---
        st.divider()
        st.subheader("🏦 Mesa de Inversión (Line Shopping)")
        
        # Buscar momios usando el nombre oficial (traductor de market_scraper)
        official_home = selected_game['home_name'].lower()
        game_odds = live_odds.get(official_home, None)
        
        if game_odds:
            st.success("✅ Líneas capturadas de Las Vegas")
            home_ml = game_odds['home_ml']
            away_ml = game_odds['away_ml']
        else:
            st.warning("⚠️ Líneas no disponibles en API. Ingresa momios manuales (-110, +120):")
            col_m1, col_m2 = st.columns(2)
            home_ml = col_m1.number_input(f"Momio {home_team}", value=-110, step=5)
            away_ml = col_m2.number_input(f"Momio {away_team}", value=-110, step=5)
            
        # Cálculos de Edge
        p_home_market = american_to_prob(home_ml)
        p_away_market = american_to_prob(away_ml)
        p_home_clean, p_away_clean = remove_vig(p_home_market, p_away_market)
        
        # Evaluar el lado sugerido por el modelo
        if res['winner'] == home_team:
            calc = calculate_edge(res['home_prob'], p_home_clean)
            target_team = home_team
            target_ml = home_ml
        else:
            calc = calculate_edge(res['away_prob'], p_away_clean)
            target_team = away_team