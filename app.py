# app.py
# MLB Quant Engine - Web Interface V11.5

import streamlit as st
from model import MLBPredictor
from financial import american_to_prob, remove_vig, calculate_edge

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MLB Quant Engine", page_icon="⚾", layout="wide")

# --- CACHÉ DEL MODELO ---
# Esto evita que el modelo reinicie las bases de datos cada vez que haces clic
@st.cache_resource
def load_predictor():
    return MLBPredictor()

st.title("🏛️ MLB Quant Engine V11.5")
st.markdown("**Core Estocástico:** NegBinomial (VMR=2.65) | **Calibración:** Regresión Isotónica")
st.divider()

predictor = load_predictor()

# --- CARGA DE JUEGOS ---
with st.spinner('Extrayendo calendario y variables climáticas...'):
    try:
        games = predictor.get_todays_games()
    except Exception as e:
        st.error(f"Error de conexión con MLB API: {e}")
        games = []

if not games:
    st.warning("No hay juegos programados para hoy.")
else:
    # --- BARRA LATERAL (SIDEBAR) ---
    st.sidebar.header("Pizarra del Día")
    
    # Crear un diccionario para el selector
    game_options = {f"{g['away_name']} @ {g['home_name']}": g for g in games}
    selected_game_str = st.sidebar.selectbox("Selecciona un juego para auditar:", list(game_options.keys()))
    selected_game = game_options[selected_game_str]
    
    st.sidebar.divider()
    st.sidebar.info("La simulación ejecuta 100,000 iteraciones estocásticas para calcular la varianza exacta del encuentro.")

    # --- MOTOR PREDICTIVO (PANEL CENTRAL) ---
    st.subheader(f"🏟️ Análisis: {selected_game['away_name']} vs {selected_game['home_name']}")
    
    with st.spinner(f'Corriendo 100,000 simulaciones Monte Carlo...'):
        res = predictor.predict_game(selected_game)
        
    # Compuertas de Seguridad
    if 'error' in res:
        st.error("🛑 ALERTA DE RIESGO SISTÉMICO")
        st.write(res['error'])
        st.write("*Operación bloqueada por el motor para proteger el capital ante datos inestables.*")
    else:
        # Layout de 3 columnas para métricas
        col1, col2, col3 = st.columns(3)
        
        home_prob = res['home_prob'] * 100
        away_prob = res['away_prob'] * 100
        
        col1.metric("Ganador Proyectado", res['winner'].upper())
        col2.metric(f"Prob. {selected_game['home_name']}", f"{home_prob:.1f}%")
        col3.metric(f"Prob. {selected_game['away_name']}", f"{away_prob:.1f}%")
        
        st.markdown(f"**Factor Clave:** `{res['key_factor']}` | **Incertidumbre:** `{res['details']['uncertainty']}`")
        st.markdown(f"**Carreraje Esperado:** {res['score']['away']:.1f} - {res['score']['home']:.1f}")
        
        # --- MÓDULO FINANCIERO (EV & KELLY) ---
        st.divider()
        st.subheader("💰 Ingesta del Mercado (Gestión de Riesgo)")
        st.markdown("Ingresa los momios americanos actuales para calcular el Criterio de Kelly.")
        
        f_col1, f_col2, f_col3 = st.columns(3)
        
        with f_col1:
            home_odds = st.number_input(f"Momio {selected_game['home_name']} (Ej: -130)", value=0, step=5)
        with f_col2:
            away_odds = st.number_input(f"Momio {selected_game['away_name']} (Ej: +110)", value=0, step=5)
            
        with f_col3:
            st.write("") # Espaciador
            st.write("")
            calculate_btn = st.button("Calcular Valor Esperado (EV)", use_container_width=True)
            
        if calculate_btn and home_odds != 0 and away_odds != 0:
            # Lógica Financiera
            raw_home = american_to_prob(home_odds)
            raw_away = american_to_prob(away_odds)
            mkt_home, mkt_away = remove_vig(raw_home, raw_away)
            
            # Cruzamos el modelo contra la probabilidad limpia del mercado
            if res['winner'] == selected_game['home_name']:
                analysis = calculate_edge(res['home_prob'], mkt_home)
                mkt_display = mkt_home * 100
            else:
                analysis = calculate_edge(res['away_prob'], mkt_away)
                mkt_display = mkt_away * 100
                
            # Mostramos el Veredicto
            st.markdown("### 📊 Veredicto Cuantitativo")
            
            if analysis['kelly'] > 0:
                st.success(f"**{analysis['verdict']}** - Se detectó ineficiencia en el mercado.")
                
                res_col1, res_col2, res_col3 = st.columns(3)
                res_col1.metric("Probabilidad Mercado", f"{mkt_display:.1f}%")
                res_col2.metric("Edge Matemático", analysis['edge_pct'])
                res_col3.metric("Fracción de Kelly (Stake)", f"{analysis['kelly']*100:.2f}%")
                
                st.info(f"**Recomendación:** Invierte el {analysis['kelly']*100:.2f}% de tu Bankroll a favor de **{res['winner']}**.")
            else:
                st.error(f"**{analysis['verdict']}** - El mercado es eficiente en esta línea.")
                st.write(f"Probabilidad de Mercado ({mkt_display:.1f}%) > Probabilidad del Modelo ({max(home_prob, away_prob):.1f}%).")
                st.warning("🚫 Se prohíbe la inversión de capital en este evento.")