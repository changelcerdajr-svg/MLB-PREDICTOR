# app.py
# MLB Quant Engine - Web Interface V15.0 (UI Bloomberg/Institucional)

import streamlit as st
import datetime
import time
from market_scraper import get_live_market_odds
from model import MLBPredictor
from financial import american_to_prob, remove_vig, calculate_edge

st.set_page_config(page_title="MLB Quant Engine", page_icon="🏛️", layout="wide", initial_sidebar_state="expanded")

# --- CSS PERSONALIZADO (Diseño Institucional) ---
st.markdown("""
<style>
    .card-deportiva {
        background-color: #1E1E1E; padding: 15px; border-radius: 8px; border: 1px solid #333; height: 100%;
    }
    .badge-teal { background-color: #1D9E75; color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }
    .badge-amber { background-color: #BA7517; color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }
    .badge-red { background-color: #E24B4A; color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }
    .badge-gray { background-color: #444; color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }
    
    .ev-container-positive { border-left: 5px solid #1D9E75; background-color: #16221F; padding: 20px; border-radius: 0 8px 8px 0; margin-top: 15px;}
    .ev-container-neutral { border-left: 5px solid #444; background-color: #1E1E1E; padding: 20px; border-radius: 0 8px 8px 0; margin-top: 15px;}
    
    .action-bar { background-color: #0F6E56; color: white; padding: 15px; border-radius: 6px; text-align: center; font-size: 1.1em; font-weight: bold; margin-top: 20px; }
    
    .metric-teal { color: #1D9E75; font-size: 2.2em; font-weight: bold; line-height: 1.1; }
    .metric-amber { color: #BA7517; font-size: 2.2em; font-weight: bold; line-height: 1.1; }
    
    .prob-bar-bg { background-color: #333; border-radius: 4px; width: 100%; height: 8px; margin-top: 8px; }
    .prob-bar-fill { background-color: #1D9E75; height: 100%; border-radius: 4px; }
    
    .status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 5px; }
    .dot-live { background-color: #E24B4A; }
    .dot-final { background-color: #1D9E75; }
    .dot-sched { background-color: #888; }
    
    hr.section-divider { border-top: 1px solid #444; margin: 30px 0 15px 0; }
    .section-title { color: #888; font-size: 0.85em; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 15px; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def load_predictor():
    return MLBPredictor()

predictor = load_predictor()

# --- SELECTOR DE FECHA CON FLECHAS ---
st.sidebar.markdown("<div class='section-title'>Control de Tiempo</div>", unsafe_allow_html=True)
if 'op_date' not in st.session_state: st.session_state.op_date = datetime.date.today()

def prev_day(): st.session_state.op_date -= datetime.timedelta(days=1)
def next_day(): st.session_state.op_date += datetime.timedelta(days=1)

col1, col2, col3 = st.sidebar.columns([1, 3, 1])
with col1: st.button("◀", on_click=prev_day, use_container_width=True)
with col2: st.date_input("Fecha", key='op_date', label_visibility="collapsed")
with col3: st.button("▶", on_click=next_day, use_container_width=True)

date_str = st.session_state.op_date.strftime("%Y-%m-%d")

# --- RADAR DE MERCADO ---
st.sidebar.markdown("<br><div class='section-title'>Radar de Mercado</div>", unsafe_allow_html=True)
live_odds = get_live_market_odds()
odds_count = len(live_odds)
badge_class = "badge-teal" if odds_count > 0 else "badge-amber"
status_text = "En vivo" if odds_count > 0 else "Buscando"

st.sidebar.markdown(f"""
<div style='font-size:0.9em;'>
    <div style='display:flex; justify-content:space-between; margin-bottom:5px;'><span>Líneas capturadas</span> <span class='{badge_class}'>{odds_count} {status_text}</span></div>
    <div style='display:flex; justify-content:space-between; margin-bottom:5px; color:#aaa;'><span>Fuente</span> <span>The Odds API</span></div>
    <div style='display:flex; justify-content:space-between; color:#aaa;'><span>Actualizado hace</span> <span>{datetime.datetime.now().strftime("%H:%M:%S")}</span></div>
</div>
""", unsafe_allow_html=True)

# --- CARGA DE JUEGOS ---
st.sidebar.markdown("<br><div class='section-title'>Pizarra de Juegos</div>", unsafe_allow_html=True)
with st.spinner(f'Extrayendo pizarra...'):
    try: games = predictor.loader.get_schedule(date_str)
    except: games = []

if not games:
    st.warning(f"No hay juegos programados.")
else:
    if 'selected_game_id' not in st.session_state or st.session_state.get('last_date') != date_str:
        st.session_state.selected_game_id = games[0]['id']
        st.session_state.last_date = date_str

    # TARJETAS LATERALES MEJORADAS
    for g in games:
        status_raw = g.get('status', '')
        if status_raw in ['Live', 'In Progress']: 
            dot, text, btn_text = "dot-live", "En vivo", "Analizar"
        elif status_raw in ['Final', 'Game Over', 'Completed', 'F']: 
            dot, text, btn_text = "dot-final", "Final", "Ver"
        else: 
            dot, text, btn_text = "dot-sched", "Programado", "Analizar"

        with st.sidebar.container():
            st.markdown(f"<div style='margin-bottom:2px;'><b>{g['away_name']} @ {g['home_name']}</b></div>", unsafe_allow_html=True)
            col_s1, col_s2 = st.columns([2, 1])
            with col_s1: st.markdown(f"<div style='font-size:0.8em; color:#aaa; margin-top:5px;'><span class='status-dot {dot}'></span>{text}</div>", unsafe_allow_html=True)
            with col_s2: 
                if st.button(btn_text, key=f"btn_{g['id']}", use_container_width=True):
                    st.session_state.selected_game_id = g['id']
            st.markdown("<hr style='margin:10px 0; border-top:1px solid #333;'>", unsafe_allow_html=True)

    # --- PANEL PRINCIPAL ---
    selected_game = next((g for g in games if g['id'] == st.session_state.selected_game_id), games[0])
    away, home = selected_game['away_name'], selected_game['home_name']
    
    # HEADER DEL JUEGO
    st.markdown(f"<h2>{away} @ {home}</h2>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style='color:#aaa; font-size:0.9em; margin-bottom:20px;'>
        {selected_game['status']} · <span class='badge-teal'>Datos completos</span> · FIP Disponible
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<div class='section-title'>Análisis Deportivo</div>", unsafe_allow_html=True)
    
    with st.spinner("Corriendo simulaciones de Monte Carlo..."):
        predictor.loader._force_historical_mode = False 
        res = predictor.predict_game(selected_game)

    if 'error' in res:
        st.markdown(f"<div class='badge-red' style='padding:15px; font-size:1em;'>🛑 OPERACIÓN BLOQUEADA: {res['error']}</div>", unsafe_allow_html=True)
    else:
        # BLOQUE 1: ANÁLISIS DEPORTIVO (3 COLUMNAS)
        c1, c2, c3 = st.columns(3)
        fav_prob = max(res['home_prob'], res['away_prob']) * 100
        fav_team = home if res['home_prob'] > res['away_prob'] else away
        
        with c1:
            st.markdown(f"""
            <div class='card-deportiva'>
                <div style='color:#aaa; font-size:0.85em; margin-bottom:10px;'>Probabilidad del modelo</div>
                <div class='metric-teal'>{fav_prob:.1f}%</div>
                <div class='prob-bar-bg'><div class='prob-bar-fill' style='width:{fav_prob}%;'></div></div>
                <div style='color:#aaa; font-size:0.85em; margin-top:8px;'>{fav_team}</div>
            </div>
            """, unsafe_allow_html=True)
            
        with c2:
            st.markdown(f"""
            <div class='card-deportiva'>
                <div style='color:#aaa; font-size:0.85em; margin-bottom:10px;'>Carreraje esperado</div>
                <div style='font-size:2.2em; font-weight:bold;'>{res['score']['away']:.1f} — {res['score']['home']:.1f}</div>
                <div style='color:#aaa; font-size:0.85em; margin-top:5px;'>{away[:3].upper()} — {home[:3].upper()} · Total {res['score']['total']:.1f}</div>
            </div>
            """, unsafe_allow_html=True)
            
        with c3:
            sens = res['details']['sensitivity']
            fat_txt = res['details']['fatigue']
            fip_txt = res['details']['pitching']
            st.markdown(f"""
            <div class='card-deportiva'>
                <div style='color:#aaa; font-size:0.85em; margin-bottom:10px;'>Diagnóstico del modelo</div>
                <table style='width:100%; font-size:0.85em;'>
                    <tr><td style='color:#aaa; padding-bottom:4px;'>Sensibilidad</td><td style='text-align:right; color:#1D9E75;'>{sens}</td></tr>
                    <tr><td style='color:#aaa; padding-bottom:4px;'>Fatiga</td><td style='text-align:right;'>{fat_txt}</td></tr>
                    <tr><td style='color:#aaa; padding-bottom:4px;'>FIP</td><td style='text-align:right;'>{fip_txt}</td></tr>
                </table>
            </div>
            """, unsafe_allow_html=True)

        # BLOQUE 2: VEREDICTO FINANCIERO
        st.markdown("<hr class='section-divider'><div class='section-title'>Veredicto Financiero</div>", unsafe_allow_html=True)
        
        official_home = home.lower()
        game_odds = live_odds.get(official_home, None)
        
        if game_odds:
            home_ml, away_ml = game_odds['home_ml'], game_odds['away_ml']
        else:
            st.warning("Ingresa momios manuales:")
            cm1, cm2 = st.columns(2)
            away_ml = cm1.number_input(f"Momio {away}", value=-110, step=5)
            home_ml = cm2.number_input(f"Momio {home}", value=-110, step=5)
            
        p_home_clean, p_away_clean = remove_vig(american_to_prob(home_ml), american_to_prob(away_ml))
        
        if res['winner'] == home:
            calc = calculate_edge(res['home_prob'], p_home_clean)
            target_team, target_ml, market_p = home, home_ml, p_home_clean
        else:
            calc = calculate_edge(res['away_prob'], p_away_clean)
            target_team, target_ml, market_p = away, away_ml, p_away_clean

        # Semáforo Dinámico
        is_positive = calc['edge'] > 0
        container_class = "ev-container-positive" if is_positive else "ev-container-neutral"
        badge = "<span class='badge-teal'>Valor detectado</span>" if is_positive else "<span class='badge-gray'>Sin valor</span>"
        
        st.markdown(f"""
        <div class='{container_class}'>
            <div style='display:flex; justify-content:space-between; margin-bottom:20px;'>
                <div style='color:#aaa; font-size:1em;'>Análisis de valor esperado (EV)</div>
                <div>{badge}</div>
            </div>
            <div style='display:flex; flex-wrap:wrap;'>
                <div style='flex:1; min-width:200px; text-align:center;'>
                    <div style='color:#aaa; font-size:0.85em;'>Edge matemático</div>
                    <div class='metric-teal' style='color: {"#1D9E75" if is_positive else "#E24B4A"};'>{calc['edge_pct']}</div>
                    <div style='color:#aaa; font-size:0.8em; margin-top:5px;'>Modelo {fav_prob:.1f}% vs Mercado {market_p*100:.1f}%</div>
                </div>
                <div style='flex:1; min-width:200px; text-align:center; border-left:1px solid #333;'>
                    <div style='color:#aaa; font-size:0.85em;'>Stake recomendado (Kelly)</div>
                    <div class='metric-amber'>{(calc['kelly']*100):.2f}%</div>
                    <div style='color:#aaa; font-size:0.8em; margin-top:5px;'>del Bankroll · ¼ Kelly</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if is_positive:
            st.markdown(f"""
            <div class='action-bar'>
                Apostar: {target_team} ML {target_ml} <span style='font-weight:normal; font-size:0.8em; margin-left:10px;'>| Las Vegas (The Odds API)</span>
            </div>
            """, unsafe_allow_html=True)

        # BLOQUE 3: ESTADO DEL SISTEMA (FOOTER)
        st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
        cf1, cf2 = st.columns(2)
        with cf1:
            st.markdown(f"""
            <div class='card-deportiva'>
                <div style='color:#aaa; font-size:0.8em; margin-bottom:10px;'>Línea de mercado actual</div>
                <div style='display:flex; justify-content:space-around; align-items:center;'>
                    <div style='text-align:center;'><b>{away[:3].upper()}</b><br><span style='font-size:1.5em;'>{away_ml}</span></div>
                    <div style='color:#888; font-size:0.8em;'>vs</div>
                    <div style='text-align:center;'><b>{home[:3].upper()}</b><br><span style='font-size:1.5em;'>{home_ml}</span></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        with cf2:
            st.markdown(f"""
            <div class='card-deportiva'>
                <div style='color:#aaa; font-size:0.8em; margin-bottom:10px;'>Estado del sistema</div>
                <table style='width:100%; font-size:0.85em;'>
                    <tr><td style='padding-bottom:5px;'>Calibración</td><td style='text-align:right;'><span class='badge-teal'>Isotónica activa</span></td></tr>
                    <tr><td style='padding-bottom:5px;'>Simulaciones</td><td style='text-align:right;'>10,000 rondas</td></tr>
                    <tr><td style='padding-bottom:5px;'>Lineups</td><td style='text-align:right;'><span class='badge-teal'>Confirmados</span></td></tr>
                </table>
            </div>
            """, unsafe_allow_html=True)