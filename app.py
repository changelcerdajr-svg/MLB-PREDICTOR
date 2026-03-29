import streamlit as st
import datetime
import json
import os
import pandas as pd
from model import MLBPredictor
from financial import american_to_prob
import tracker

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MLB Quant Engine V17.3", page_icon="⚾", layout="wide", initial_sidebar_state="expanded")

# --- CONSTANTES DE RIESGO ---
CONFIDENCE_THRESHOLD = 0.55
MAX_ODDS_LIMIT = -250
KELLY_FRACTION = 0.25

# --- CSS PERSONALIZADO (Restaurando UI Completa) ---
st.markdown("""
<style>
    .card-deportiva { background-color: #1C1C1E; padding: 20px; border-radius: 16px; border: 1px solid #2C2C2E; box-shadow: 0 4px 15px rgba(0,0,0,0.3); margin-bottom: 20px; transition: transform 0.2s; }
    .card-deportiva:hover { transform: translateY(-2px); border-color: #3A3A3C; }
    .badge-blue { background-color: #0066FF; color: white; padding: 6px 12px; border-radius: 12px; font-size: 0.8em; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; }
    .badge-green { background-color: #19B664; color: white; padding: 6px 12px; border-radius: 12px; font-size: 0.8em; font-weight: 800; text-transform: uppercase; }
    .badge-red { background-color: #FF3B30; color: white; padding: 6px 12px; border-radius: 12px; font-size: 0.8em; font-weight: 800; text-transform: uppercase; }
    .badge-warning { background-color: #FF9500; color: white; padding: 6px 12px; border-radius: 12px; font-size: 0.8em; font-weight: 800; text-transform: uppercase; }
    .team-name { font-size: 1.6em; font-weight: 800; color: #FFFFFF; margin: 5px 0 2px 0; letter-spacing: -0.5px;}
    .pitcher-name { font-size: 0.9em; color: #8E8E93; margin-bottom: 10px; font-weight: 500;}
    .score-proj { font-size: 1.4em; font-weight: 800; color: #32D74B; float: right;}
    .stat-row { display: flex; justify-content: space-between; border-bottom: 1px solid #2C2C2E; padding: 10px 0; font-size: 0.95em; color: #E5E5EA;}
    .stat-row:last-child { border-bottom: none; }
    .section-divider { border-top: 2px solid #333; margin: 40px 0; }
    .section-title { font-size: 1.8em; font-weight: 800; margin-bottom: 25px; color: #FFF; letter-spacing: -0.5px;}
    .kelly-recommendation { background-color: rgba(25, 182, 100, 0.1); border-left: 4px solid #19B664; padding: 15px; margin-top: 20px; border-radius: 6px;}
    .no-edge-box { background-color: rgba(255, 59, 48, 0.1); border-left: 4px solid #FF3B30; padding: 15px; margin-top: 20px; border-radius: 6px;}
    .detail-box { background-color: #2C2C2E; padding: 12px; border-radius: 8px; margin-top: 10px; font-size: 0.85em; color: #D1D1D6;}
    .metric-value { font-family: 'Courier New', Courier, monospace; font-weight: bold; color: #0A84FF;}
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

def format_odds(american):
    if american > 0: return f"+{american}"
    return str(american)

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
            if ml_list:
                line = ml_list[0].get('currentLine')
                if line: return line.get('homeOdds'), line.get('awayOdds')
    return None, None

# --- INICIALIZACIÓN DE DATOS ---
st.title("⚾ Terminal de Operaciones Cuantitativas MLB")
st.markdown("Motor Estocástico V17.3 | Integradora Statcast & Gestión Kelly Criterion")

@st.cache_resource
def get_predictor():
    return MLBPredictor(use_calibrator=False)

predictor = get_predictor()
odds_data = load_live_odds()
today_str = datetime.datetime.now().strftime("%Y-%m-%d")

games = predictor.loader.get_schedule(today_str)

# --- BARRA LATERAL (CONFIGURACIÓN Y STATUS) ---
with st.sidebar:
    st.image("https://www.mlbstatic.com/team-logos/league-on-dark/1.svg", width=150)
    st.header("⚙️ Gestión de Capital")
    bankroll = st.number_input("Bankroll Operativo ($)", value=1000.0, step=100.0, format="%.2f")
    
    st.markdown("---")
    st.header("📡 Status del Sistema")
    if not odds_data:
        st.error("⚠️ Líneas Desconectadas. Ejecuta el scraper localmente.")
    else:
        st.success("✅ Conexión a Mercado Estable")
        st.write(f"📊 Líneas Extraídas: {len(odds_data.get(today_str, []))}")
    
    st.write(f"⚾ Juegos Programados: {len(games) if games else 0}")
    
    st.markdown("---")
    st.markdown("### Parámetros de Riesgo")
    st.write(f"🎯 **Confianza Mínima:** {CONFIDENCE_THRESHOLD*100}%")
    st.write(f"🛑 **Límite de Momio:** {MAX_ODDS_LIMIT}")
    st.write(f"⚖️ **Kelly Fraction:** {KELLY_FRACTION}x")

# --- SECCIÓN PRINCIPAL: PIZARRA DE JUEGOS ---
st.markdown("<div class='section-title'>🎯 Panel de Inversión Diaria</div>", unsafe_allow_html=True)

if not games:
    st.info("No hay juegos programados en la MLB para la fecha actual.")
else:
    # Usamos un layout dinámico de columnas
    col1, col2 = st.columns(2)
    
    for idx, g in enumerate(games):
        if g['status'] in ['Final', 'In Progress']: continue
        
        # Obtener momios del JSON
        h_odds, a_odds = get_today_odds(odds_data, today_str, g['home_name'])
        
        # Generar Predicción
        with st.spinner(f"Analizando {g['away_name']} vs {g['home_name']}..."):
            res = predictor.predict_game(g)
        
        if 'error' in res:
            with (col1 if idx % 2 == 0 else col2):
                st.error(f"Faltan datos de Statcast para {g['away_name']} @ {g['home_name']}")
            continue

        prob = res['confidence']
        pick = res['winner']
        
        # Determinar status visual
        if prob >= CONFIDENCE_THRESHOLD:
            badge_class = "badge-green"
            status_text = "SEÑAL ACTIVA"
        else:
            badge_class = "badge-warning"
            status_text = "RIESGO ALTO (BAJA CONFIANZA)"
            
        with (col1 if idx % 2 == 0 else col2):
            st.markdown(f"""
            <div class='card-deportiva'>
                <div>
                    <span class='{badge_class}'>{status_text}</span>
                    <span style='float:right; color:#8E8E93; font-size:0.8em;'>{g.get('game_time', 'TBD')}</span>
                </div>
                
                <div style='margin-top: 15px;'>
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <div class='team-name'>{g['away_name']}</div>
                        <div class='score-proj'>{res['score']['away']:.1f}</div>
                    </div>
                    <div class='pitcher-name'>Probable: {g['away_pitcher']}</div>
                    
                    <div style='display: flex; justify-content: space-between; align-items: center; margin-top: 5px;'>
                        <div class='team-name'>@ {g['home_name']}</div>
                        <div class='score-proj'>{res['score']['home']:.1f}</div>
                    </div>
                    <div class='pitcher-name'>Probable: {g['home_pitcher']}</div>
                </div>
                
                <div style='margin-top: 15px; border-top: 1px solid #2C2C2E; padding-top: 15px;'>
                    <div class='stat-row'>
                        <span>Pick del Modelo:</span>
                        <span style='color: #FFFFFF; font-weight: bold; font-size: 1.1em;'>{pick}</span>
                    </div>
                    <div class='stat-row'>
                        <span>Probabilidad de Victoria:</span>
                        <span style='color: #32D74B; font-weight: bold; font-size: 1.1em;'>{prob*100:.1f}%</span>
                    </div>
                    <div class='stat-row'>
                        <span>Total Proyectado (O/U):</span>
                        <span style='color: #0A84FF; font-weight: bold;'>{res['score']['total']:.1f} Carreras</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # Expandible para Análisis Profundo (Restaurando funciones antiguas)
            with st.expander("🔬 Desglose Cuantitativo y Statcast"):
                st.markdown(f"""
                <div class='detail-box'>
                    <b>Pitcheo (xERA Bayesiano):</b><br>
                    {res['details']['pitching']}<br><br>
                    <b>Poder Ofensivo (xwOBA):</b><br>
                    {res['details']['offense']}<br><br>
                    <b>Factores Estructurales:</b><br>
                    {res['details']['environment']}<br>
                    <i>Sensibilidad: {res['details']['sensitivity']}</i>
                </div>
                """, unsafe_allow_html=True)
            
            # Sección Financiera
            if h_odds is not None:
                curr_odds = h_odds if pick == g['home_name'] else a_odds
                market_prob = american_to_prob(curr_odds)
                edge = prob - market_prob
                
                st.markdown(f"""
                    <div class='stat-row' style='margin-top:10px;'>
                        <span>Línea DraftKings:</span>
                        <b style='color:#FFF;'>{format_odds(curr_odds)}</b>
                    </div>
                    <div class='stat-row'>
                        <span>Probabilidad Implícita Casino:</span>
                        <b>{market_prob*100:.1f}%</b>
                    </div>
                    <div class='stat-row'>
                        <span>Edge (Ventaja Matemática):</span>
                        <b style='color: {"#32D74B" if edge > 0 else "#FF3B30"};'>{edge*100:+.2f}%</b>
                    </div>
                """, unsafe_allow_html=True)
                
                # Evaluación de Kelly y Ejecución
                if prob >= CONFIDENCE_THRESHOLD:
                    if curr_odds >= 0 or curr_odds >= MAX_ODDS_LIMIT:
                        stake_pct = calculate_kelly(prob, curr_odds)
                        if stake_pct > 0:
                            stake_amount = bankroll * stake_pct
                            st.markdown(f"""
                            <div class='kelly-recommendation'>
                                <h4 style='margin:0; color:#19B664;'>💡 APROBACIÓN DE INVERSIÓN</h4>
                                <div style='margin-top: 5px; font-size: 1.1em; color: #FFF;'>
                                    Recomendación {KELLY_FRACTION}x Kelly: <b>${stake_amount:.2f}</b><br>
                                    <span style='font-size: 0.85em; color: #D1D1D6;'>({stake_pct*100:.2f}% del Bankroll Total)</span>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Botón de Registro en Tracker
                            btn_key = f"btn_{g['home_name'].replace(' ', '_')}"
                            if st.button("💾 Registrar Operación en Bitácora", key=btn_key, use_container_width=True):
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
                                    st.success("Operación guardada exitosamente en history_log.csv")
                                else:
                                    st.warning("Esta operación ya fue registrada el día de hoy.")
                        else:
                            st.markdown("<div class='no-edge-box'><b>⚠️ RIESGO MATEMÁTICO:</b> Edge Negativo bajo Criterio de Kelly. (Mercado Eficiente)</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='no-edge-box'><b>⛔ LÍMITE DE EXPOSICIÓN:</b> Momio ({curr_odds}) demasiado caro. Supera el límite de {MAX_ODDS_LIMIT}.</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='no-edge-box' style='border-left-color: #FF9500;'><b>⏳ MERCADO CERRADO:</b> Esperando apertura de líneas de Las Vegas.</div>", unsafe_allow_html=True)
                
            st.markdown("</div>", unsafe_allow_html=True)

# --- SECCIÓN: TRACK RECORD (HISTORIAL INSTITUCIONAL) ---
st.markdown("<hr class='section-divider'><div class='section-title'>📊 Auditoría de Rendimiento (CLV Track Record)</div>", unsafe_allow_html=True)

try:
    df_log = tracker.load_tracker()
    
    if not df_log.empty:
        df_log['Fecha'] = pd.to_datetime(df_log['Fecha'])
        df_log = df_log.sort_values(by='Fecha', ascending=False).reset_index(drop=True)
        
        ganados = len(df_log[df_log['Resultado'] == 'Ganado'])
        perdidos = len(df_log[df_log['Resultado'] == 'Perdido'])
        pendientes = len(df_log[df_log['Resultado'] == 'Pendiente'])
        total_cerrados = ganados + perdidos
        
        win_rate = (ganados / total_cerrados * 100) if total_cerrados > 0 else 0.0
        
        # Métricas rápidas
        met1, met2, met3, met4 = st.columns(4)
        met1.metric("Win Rate Histórico", f"{win_rate:.1f}%", f"{ganados}G - {perdidos}P")
        met2.metric("Juegos Pendientes", pendientes)
        met3.metric("Promedio de Confianza", f"{df_log['Confianza (%)'].mean():.1f}%")
        met4.metric("Edge Promedio Capturado", f"{df_log['Edge'].mean():+.2f}%")
        
        st.markdown("### Bitácora Editable")
        st.caption("Instrucciones: Haz doble clic en la columna 'Resultado' para calificar los picks como 'Ganado' o 'Perdido'.")
        
        edited_df = st.data_editor(
            df_log, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Resultado": st.column_config.SelectboxColumn(
                    "Resultado del Juego",
                    help="Actualiza el status de la apuesta",
                    options=["Pendiente", "Ganado", "Perdido"],
                    required=True
                )
            }
        )
        
        if st.button("💾 Guardar Actualizaciones del Historial", use_container_width=True):
            edited_df.to_csv(tracker.FILE, index=False)
            st.success("¡Base de datos actualizada con éxito!")
            
    else:
        st.info("La bitácora de operaciones está vacía. Registra tu primera operación para comenzar a medir tu Alpha.")
except Exception as e:
    st.error(f"Error al cargar el Tracker Institucional: {e}")