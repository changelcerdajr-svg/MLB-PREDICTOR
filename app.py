# app.py
# MLB Quant Engine - Web Interface V17.3 (Soberanía de Datos y Kelly Criterion)

import streamlit as st
import datetime
import json
import os
from model import MLBPredictor
from financial import american_to_prob
import tracker 

st.set_page_config(page_title="MLB Quant Engine V17", page_icon="⚾", layout="wide", initial_sidebar_state="expanded")

# --- CONSTANTES DE RIESGO ---
CONFIDENCE_THRESHOLD = 0.55
MAX_ODDS_LIMIT = -250
KELLY_FRACTION = 0.25

# --- CSS PERSONALIZADO ---
st.markdown("""
<style>
    .card-deportiva { background-color: #1C1C1E; padding: 18px; border-radius: 16px; border: 1px solid #2C2C2E; height: 100%; box-shadow: 0 4px 10px rgba(0,0,0,0.2); margin-bottom: 15px;}
    .badge-blue { background-color: #0066FF; color: white; padding: 5px 10px; border-radius: 12px; font-size: 0.75em; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; }
    .badge-green { background-color: #19B664; color: white; padding: 5px 10px; border-radius: 12px; font-size: 0.75em; font-weight: 800; text-transform: uppercase; }
    .badge-red { background-color: #FF3B30; color: white; padding: 5px 10px; border-radius: 12px; font-size: 0.75em; font-weight: 800; text-transform: uppercase; }
    .team-name { font-size: 1.4em; font-weight: 700; color: #FFFFFF; margin: 10px 0 5px 0;}
    .pitcher-name { font-size: 0.85em; color: #8E8E93; margin-bottom: 15px;}
    .stat-row { display: flex; justify-content: space-between; border-bottom: 1px solid #2C2C2E; padding: 8px 0; font-size: 0.9em; color: #E5E5EA;}
    .section-divider { border-top: 2px solid #333; margin: 30px 0; }
    .section-title { font-size: 1.5em; font-weight: bold; margin-bottom: 20px; color: #FFF; }
    .kelly-recommendation { background-color: rgba(25, 182, 100, 0.1); border-left: 4px solid #19B664; padding: 10px; margin-top: 15px; border-radius: 4px;}
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES AUXILIARES ---
@st.cache_data(ttl=60)
def load_live_odds():
    try:
        with open('data_odds/live_odds.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def american_to_decimal(american):
    if american > 0: return (american / 100) + 1
    return (100 / abs(american)) + 1

def calculate_kelly(prob_win, american_odds):
    b = american_to_decimal(american_odds) - 1
    q = 1 - prob_win
    f_star = (b * prob_win - q) / b
    return max(0, f_star * KELLY_FRACTION)

def get_today_odds(odds_data, date_str, mlb_home_name):
    day_games = odds_data.get(date_str, [])
    if not day_games: return None, None
    mlb_clean = mlb_home_name.lower().strip()
    
    for game in day_games:
        dk_name = game.get('gameView', {}).get('homeTeam', {}).get('fullName', '').lower().strip()
        if mlb_clean in dk_name or dk_name in mlb_clean:
            ml_list = game.get('odds', {}).get('moneyline', [])
            for book in ml_list:
                if book.get('sportsbook') == 'draftkings':
                    line = book.get('currentLine')
                    if line: return line.get('homeOdds'), line.get('awayOdds')
    return None, None

# --- INICIALIZACIÓN ---
st.title("⚾ Terminal MLB Quant V17.3")
st.markdown("Motor de Predicción Estocástica y Gestión de Riesgo Institucional")

predictor = MLBPredictor(use_calibrator=False) # Usamos modelo en crudo para Alpha Real
odds_data = load_live_odds()
today_str = datetime.datetime.now().strftime("%Y-%m-%d")

games = predictor.loader.get_schedule(today_str)

# --- SIDEBAR: PANEL DE CONTROL ---
with st.sidebar:
    st.header("⚙️ Configuración del Bankroll")
    bankroll = st.number_input("Capital Operativo ($)", value=1000.0, step=100.0)
    st.markdown("---")
    st.markdown("### Estado del Sistema")
    if not odds_data:
        st.error("⚠️ Datos de mercado desconectados. Ejecuta `python live_odds_scraper.py` en tu terminal.")
    else:
        st.success("✅ Momios de DraftKings Sincronizados")
        st.write(f"Partidos extraídos: {len(odds_data.get(today_str, []))}")
    st.write(f"Juegos MLB Hoy: {len(games) if games else 0}")

# --- SECCIÓN DE PREDICCIONES DIARIAS ---
st.markdown("<div class='section-title'>🎯 Pizarra de Operaciones de Hoy</div>", unsafe_allow_html=True)

if not games:
    st.info("No hay juegos programados en la MLB para el día de hoy.")
else:
    cols = st.columns(3)
    col_idx = 0

    for g in games:
        if g['status'] in ['Final', 'In Progress']: continue
        
        # Cruzar con JSON Local
        h_odds, a_odds = get_today_odds(odds_data, today_str, g['home_name'])
        
        res = predictor.predict_game(g)
        if 'error' in res: continue

        prob = res['confidence']
        pick = res['winner']
        
        # Tarjeta Visual
        with cols[col_idx % 3]:
            # Lógica de Color del Badge
            if prob >= CONFIDENCE_THRESHOLD:
                badge_class = "badge-green"
                status_text = "VENTAJA MATEMÁTICA"
            else:
                badge_class = "badge-red"
                status_text = "NO BET (BAJA CONFIANZA)"
                
            st.markdown(f"""
            <div class='card-deportiva'>
                <span class='{badge_class}'>{status_text}</span>
                <div style='margin-top:10px;'>
                    <div class='team-name'>{g['away_name']}</div>
                    <div class='pitcher-name'>P: {g['away_pitcher']}</div>
                    <div class='team-name'>@ {g['home_name']}</div>
                    <div class='pitcher-name'>P: {g['home_pitcher']}</div>
                </div>
            """, unsafe_allow_html=True)
            
            # Estadísticas internas
            st.markdown(f"""
                <div class='stat-row'><span>Predicción Modelo:</span> <b>{pick}</b></div>
                <div class='stat-row'><span>Probabilidad de Victoria:</span> <b>{prob*100:.1f}%</b></div>
            """, unsafe_allow_html=True)
            
            # Renderizado Financiero si hay momios
            if h_odds is not None:
                curr_odds = h_odds if pick == g['home_name'] else a_odds
                market_prob = american_to_prob(curr_odds)
                edge = prob - market_prob
                
                st.markdown(f"""
                    <div class='stat-row'><span>Momio DraftKings:</span> <b>{curr_odds}</b></div>
                    <div class='stat-row'><span>Edge vs Mercado:</span> <b>{edge*100:+.1f}%</b></div>
                """, unsafe_allow_html=True)
                
                # Evaluación de Inversión
                if prob >= CONFIDENCE_THRESHOLD and (curr_odds >= 0 or curr_odds >= MAX_ODDS_LIMIT):
                    stake_pct = calculate_kelly(prob, curr_odds)
                    if stake_pct > 0:
                        stake_amount = bankroll * stake_pct
                        st.markdown(f"""
                        <div class='kelly-recommendation'>
                            <b>💡 SUGERENCIA KELLY (0.25x):</b><br>
                            Apostar ${stake_amount:.2f} ({stake_pct*100:.2f}% del Bankroll)
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Botón para registrar rápido en el tracker
                        if st.button(f"📝 Registrar Apuesta", key=f"btn_{g['home_name']}"):
                            saved = tracker.log_bet(
                                fecha=today_str,
                                juego=f"{g['away_name']} @ {g['home_name']}",
                                pick=pick,
                                confianza=prob*100,
                                prob_mercado=market_prob,
                                cuota=curr_odds,
                                edge=round(edge*100, 2)
                            )
                            if saved:
                                st.success("¡Registrado en history_log.csv!")
                            else:
                                st.warning("Ya estaba registrado.")
                    else:
                        st.markdown("<div style='margin-top:10px; color:#FF3B30; font-size:0.9em;'>❌ Sin Edge Financiero (Momio muy castigado)</div>", unsafe_allow_html=True)
                elif curr_odds < MAX_ODDS_LIMIT:
                    st.markdown(f"<div style='margin-top:10px; color:#FF3B30; font-size:0.9em;'>❌ Momio excede límite de riesgo ({MAX_ODDS_LIMIT})</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div style='margin-top:10px; color:#FF9500; font-size:0.9em;'>⏳ Esperando líneas de apertura...</div>", unsafe_allow_html=True)
                
            st.markdown("</div>", unsafe_allow_html=True)
        col_idx += 1

# --- SECCIÓN DEL TRACK RECORD ---
st.markdown("<hr class='section-divider'><div class='section-title'>📊 Tu Récord Histórico de Operaciones</div>", unsafe_allow_html=True)

df_log = tracker.load_tracker()

if not df_log.empty:
    ganados = len(df_log[df_log['Resultado'] == 'Ganado'])
    perdidos = len(df_log[df_log['Resultado'] == 'Perdido'])
    total_cerrados = ganados + perdidos
    win_rate = (ganados / total_cerrados * 100) if total_cerrados > 0 else 0
    
    c_t1, c_t2, c_t3 = st.columns(3)
    c_t1.metric("Win Rate Real", f"{win_rate:.1f}%")
    c_t2.metric("Ganados", ganados)
    c_t3.metric("Perdidos", perdidos)
    
    st.caption("Haz doble clic en la columna 'Resultado' para marcar tus juegos como 'Ganado' o 'Perdido'.")
    
    edited_df = st.data_editor(df_log, use_container_width=True, hide_index=True)
    
    if st.button("Guardar Cambios en Historial", use_container_width=True):
        edited_df.to_csv(tracker.FILE, index=False)
        st.success("Historial actualizado correctamente.")
else:
    st.info("Tu historial de apuestas está vacío. Las apuestas que apruebes aparecerán aquí para medir tu CLV.")