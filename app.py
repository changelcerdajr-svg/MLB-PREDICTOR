# app.py
# MLB Quant Engine - Web Interface V15.4 (Con Monitor de Efectividad Diaria)

import streamlit as st
import datetime
import time
from market_scraper import get_live_market_odds
from model import MLBPredictor
from financial import american_to_prob, remove_vig, calculate_edge
import tracker # Importamos el gestor de bitácora

st.set_page_config(page_title="MLB Quant Engine", page_icon="⚾", layout="wide", initial_sidebar_state="expanded")

# --- CSS PERSONALIZADO (Estilo theScore) ---
st.markdown("""
<style>
    .card-deportiva { background-color: #1C1C1E; padding: 18px; border-radius: 16px; border: 1px solid #2C2C2E; height: 100%; box-shadow: 0 4px 10px rgba(0,0,0,0.2); }
    .badge-blue { background-color: #0066FF; color: white; padding: 5px 10px; border-radius: 12px; font-size: 0.75em; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; }
    .badge-green { background-color: #19B664; color: white; padding: 5px 10px; border-radius: 12px; font-size: 0.75em; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; }
    .badge-red { background-color: #FF3333; color: white; padding: 5px 10px; border-radius: 12px; font-size: 0.75em; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; }
    .badge-amber { background-color: #F5A623; color: white; padding: 5px 10px; border-radius: 12px; font-size: 0.75em; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; }
    .badge-gray { background-color: #2C2C2E; color: #E5E5EA; padding: 5px 10px; border-radius: 12px; font-size: 0.75em; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; }
    .ev-container-positive { border-left: 6px solid #19B664; background-color: #14221A; padding: 20px; border-radius: 0 16px 16px 0; margin-top: 15px; }
    .ev-container-neutral { border-left: 6px solid #2C2C2E; background-color: #1C1C1E; padding: 20px; border-radius: 0 16px 16px 0; margin-top: 15px; }
    .action-bar { background-color: #0066FF; color: white; padding: 18px; border-radius: 14px; text-align: center; font-size: 1.15em; font-weight: 900; margin-top: 20px; box-shadow: 0 4px 15px rgba(0, 102, 255, 0.35); letter-spacing: 0.5px;}
    .metric-blue { color: #337AEE; font-size: 2.6em; font-weight: 900; line-height: 1.1; }
    .metric-green { color: #19B664; font-size: 2.6em; font-weight: 900; line-height: 1.1; }
    .metric-amber { color: #F5A623; font-size: 2.6em; font-weight: 900; line-height: 1.1; }
    .prob-bar-bg { background-color: #2C2C2E; border-radius: 6px; width: 100%; height: 10px; margin-top: 12px; overflow: hidden; }
    .prob-bar-fill { background-color: #0066FF; height: 100%; border-radius: 6px; }
    .status-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
    .dot-live { background-color: #FF3333; box-shadow: 0 0 8px rgba(255,51,51,0.8); }
    .dot-final { background-color: #19B664; }
    .dot-sched { background-color: #8E8E93; }
    hr.section-divider { border-top: 1px solid #2C2C2E; margin: 35px 0 20px 0; }
    .section-title { color: #8E8E93; font-size: 0.85em; font-weight: 800; letter-spacing: 1.2px; text-transform: uppercase; margin-bottom: 18px; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def load_predictor():
    return MLBPredictor()

predictor = load_predictor()

# --- CACHÉ DE EFECTIVIDAD DIARIA (Actualiza cada 5 mins para no trabar la app) ---
@st.cache_data(ttl=300)
def get_daily_accuracy(date_str, _games_list, _predictor_obj):
    finished = [g for g in _games_list if g.get('status', '') in ['Final', 'Game Over', 'Completed', 'F']]
    correct = 0
    evaluated = 0
    for fg in finished:
        res = _predictor_obj.predict_game(fg)
        if 'error' not in res:
            evaluated += 1
            if res['winner'] == fg['real_winner']:
                correct += 1
    return correct, evaluated, len(finished)

# --- SELECTOR DE FECHA ---
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
badge_class = "badge-blue" if odds_count > 0 else "badge-amber"
status_text = "En vivo" if odds_count > 0 else "Buscando"

st.sidebar.markdown(f"""
<div style='font-size:0.9em; background-color:#1C1C1E; padding:15px; border-radius:12px; border:1px solid #2C2C2E;'>
    <div style='display:flex; justify-content:space-between; margin-bottom:8px;'><span style='font-weight:bold;'>Líneas activas</span> <span class='{badge_class}'>{odds_count} {status_text}</span></div>
    <div style='display:flex; justify-content:space-between; margin-bottom:8px; color:#8E8E93;'><span>Fuente</span> <span>The Odds API</span></div>
    <div style='display:flex; justify-content:space-between; color:#8E8E93;'><span>Actualizado</span> <span>{datetime.datetime.now().strftime("%H:%M:%S")}</span></div>
</div>
""", unsafe_allow_html=True)

# --- CARGA DE JUEGOS ---
with st.spinner(f'Extrayendo pizarra de {date_str}...'):
    try: games = predictor.loader.get_schedule(date_str)
    except: games = []

# --- NUEVO: MONITOR DE JORNADA ---
st.sidebar.markdown("<br><div class='section-title'>Monitor de Jornada (Global)</div>", unsafe_allow_html=True)
if games:
    correct_preds, evaluated_games, finished_count = get_daily_accuracy(date_str, games, predictor)
    
    if evaluated_games > 0:
        win_pct = (correct_preds / evaluated_games) * 100
        color_acc = "#19B664" if win_pct >= 53 else "#F5A623" if win_pct >= 50 else "#FF3333"
        st.sidebar.markdown(f"""
        <div style='background-color:#1C1C1E; padding:15px; border-radius:12px; border:1px solid #2C2C2E; text-align:center;'>
            <div style='color:#8E8E93; font-size:0.85em; font-weight:bold; text-transform:uppercase;'>Aciertos del Modelo (Hoy)</div>
            <div style='font-size:2.2em; font-weight:900; color:{color_acc};'>{correct_preds} <span style='color:#8E8E93; font-size:0.5em;'>de</span> {evaluated_games}</div>
            <div style='color:#E5E5EA; font-size:0.95em; font-weight:bold;'>Efectividad: {win_pct:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.sidebar.markdown("<div style='color:#8E8E93; font-size:0.85em; font-style:italic; text-align:center;'>Esperando a que finalicen los primeros juegos de hoy...</div>", unsafe_allow_html=True)
else:
    st.sidebar.warning(f"No hay juegos para el {date_str}.")

# --- PIZARRA DE JUEGOS (TARJETAS) ---
st.sidebar.markdown("<br><div class='section-title'>Pizarra de Juegos</div>", unsafe_allow_html=True)
if games:
    if 'selected_game_id' not in st.session_state or st.session_state.get('last_date') != date_str:
        st.session_state.selected_game_id = games[0]['id']
        st.session_state.last_date = date_str

    for g in games:
        status_raw = g.get('status', '')
        if status_raw in ['Live', 'In Progress']: 
            dot, text, btn_text = "dot-live", "En vivo", "Analizar"
        elif status_raw in ['Final', 'Game Over', 'Completed', 'F']: 
            dot, text, btn_text = "dot-final", "Final", "Ver"
        else: 
            dot, text, btn_text = "dot-sched", "Programado", "Analizar"

        with st.sidebar.container():
            st.markdown(f"<div style='margin-bottom:2px; font-size:1.05em;'><b>{g['away_name']} @ {g['home_name']}</b></div>", unsafe_allow_html=True)
            col_s1, col_s2 = st.columns([2, 1])
            with col_s1: st.markdown(f"<div style='font-size:0.85em; color:#8E8E93; margin-top:8px; font-weight:bold;'><span class='status-dot {dot}'></span>{text}</div>", unsafe_allow_html=True)
            with col_s2: 
                if st.button(btn_text, key=f"btn_{g['id']}", use_container_width=True):
                    st.session_state.selected_game_id = g['id']
            st.markdown("<hr style='margin:12px 0; border-top:1px solid #2C2C2E;'>", unsafe_allow_html=True)

    # --- PANEL PRINCIPAL ---
    selected_game = next((g for g in games if g['id'] == st.session_state.selected_game_id), games[0])
    away, home = selected_game['away_name'], selected_game['home_name']
    
    st.markdown(f"<h1 style='font-size:2.2em; margin-bottom:5px;'>{away} @ {home}</h1>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style='color:#8E8E93; font-size:0.95em; font-weight:bold; margin-bottom:25px;'>
        {selected_game['status']} &nbsp;·&nbsp; <span class='badge-blue'>Datos completos</span> &nbsp;·&nbsp; FIP Disponible
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<div class='section-title'>Análisis Deportivo</div>", unsafe_allow_html=True)
    
    with st.spinner("Corriendo simulaciones de Monte Carlo..."):
        predictor.loader._force_historical_mode = False 
        res = predictor.predict_game(selected_game)

    if 'error' in res:
        st.markdown(f"<div class='badge-red' style='padding:20px; font-size:1.1em; border-radius:12px;'>Error Crítico: {res['error']}</div>", unsafe_allow_html=True)
    else:
        # BLOQUE 1: PROBABILIDADES Y MARCADOR
        c1, c2, c3 = st.columns(3)
        fav_prob = max(res['home_prob'], res['away_prob']) * 100
        fav_team = home if res['home_prob'] > res['away_prob'] else away
        
        with c1:
            st.markdown(f"""
            <div class='card-deportiva'>
                <div style='color:#8E8E93; font-size:0.85em; font-weight:bold; text-transform:uppercase; margin-bottom:12px;'>Probabilidad del modelo</div>
                <div class='metric-blue'>{fav_prob:.1f}%</div>
                <div class='prob-bar-bg'><div class='prob-bar-fill' style='width:{fav_prob}%;'></div></div>
                <div style='color:#E5E5EA; font-size:0.95em; font-weight:bold; margin-top:10px;'>{fav_team}</div>
            </div>
            """, unsafe_allow_html=True)
            
        with c2:
            st.markdown(f"""
            <div class='card-deportiva'>
                <div style='color:#8E8E93; font-size:0.85em; font-weight:bold; text-transform:uppercase; margin-bottom:12px;'>Carreraje esperado</div>
                <div style='font-size:2.4em; font-weight:900;'>{res['score']['away']:.1f} — {res['score']['home']:.1f}</div>
                <div style='color:#E5E5EA; font-size:0.95em; font-weight:bold; margin-top:5px;'>{away[:3].upper()} — {home[:3].upper()} <span style='color:#8E8E93;'>· Total {res['score']['total']:.1f}</span></div>
            </div>
            """, unsafe_allow_html=True)
            
        with c3:
            sens = res['details']['sensitivity']
            fat_txt = res['details']['fatigue']
            fip_txt = res['details']['pitching']
            st.markdown(f"""
            <div class='card-deportiva'>
                <div style='color:#8E8E93; font-size:0.85em; font-weight:bold; text-transform:uppercase; margin-bottom:12px;'>Diagnóstico interno</div>
                <table style='width:100%; font-size:0.95em; font-weight:600; color:#E5E5EA;'>
                    <tr><td style='color:#8E8E93; padding-bottom:8px;'>Sensibilidad</td><td style='text-align:right; color:#19B664;'>{sens}</td></tr>
                    <tr><td style='color:#8E8E93; padding-bottom:8px;'>Fatiga</td><td style='text-align:right;'>{fat_txt}</td></tr>
                    <tr><td style='color:#8E8E93; padding-bottom:8px;'>FIP</td><td style='text-align:right;'>{fip_txt}</td></tr>
                </table>
            </div>
            """, unsafe_allow_html=True)

        # BLOQUE 2: VEREDICTO FINANCIERO Y KELLY
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

        is_positive = calc['edge'] > 0
        container_class = "ev-container-positive" if is_positive else "ev-container-neutral"
        badge = "<span class='badge-green'>Edge Detectado</span>" if is_positive else "<span class='badge-gray'>Sin Valor Matemático</span>"
        
        st.markdown(f"""
        <div class='{container_class}'>
            <div style='display:flex; justify-content:space-between; margin-bottom:20px; align-items:center;'>
                <div style='color:#E5E5EA; font-size:1.1em; font-weight:bold;'>Análisis de Valor Esperado (EV)</div>
                <div>{badge}</div>
            </div>
            <div style='display:flex; flex-wrap:wrap;'>
                <div style='flex:1; min-width:200px; text-align:center;'>
                    <div style='color:#8E8E93; font-size:0.85em; font-weight:bold; text-transform:uppercase;'>Ventaja Matemática</div>
                    <div class='metric-green' style='color: {"#19B664" if is_positive else "#FF3333"};'>{calc['edge_pct']}</div>
                    <div style='color:#8E8E93; font-size:0.85em; margin-top:8px; font-weight:bold;'>Modelo {fav_prob:.1f}% vs Mercado {market_p*100:.1f}%</div>
                </div>
                <div style='flex:1; min-width:200px; text-align:center; border-left:1px solid #2C2C2E;'>
                    <div style='color:#8E8E93; font-size:0.85em; font-weight:bold; text-transform:uppercase;'>Riesgo (Kelly)</div>
                    <div class='metric-amber'>{(calc['kelly']*100):.2f}%</div>
                    <div style='color:#8E8E93; font-size:0.85em; margin-top:8px; font-weight:bold;'>del Bankroll · ¼ Kelly</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # --- BOTÓN DE GUARDADO (TRACKER) ---
        if is_positive:
            st.markdown(f"""
            <div class='action-bar'>
                Apostar a {target_team} ML ({target_ml}) <span style='font-weight:normal; font-size:0.85em; margin-left:12px; color:rgba(255,255,255,0.7);'>| The Odds API</span>
            </div>
            """, unsafe_allow_html=True)
            
            st.write("") 
            if st.button("💾 Guardar Predicción en Bitácora", use_container_width=True):
                guardado = tracker.log_bet(date_str, f"{away} @ {home}", target_team, fav_prob, target_ml, calc['edge_pct'])
                if guardado:
                    st.success("¡Operación registrada en tu historial de operaciones!")
                else:
                    st.warning("Este juego ya estaba guardado en tu bitácora de hoy.")

        # BLOQUE 3: ESTRUCTURA
        st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
        cf1, cf2 = st.columns(2)
        with cf1:
            st.markdown(f"""
            <div class='card-deportiva'>
                <div style='color:#8E8E93; font-size:0.85em; font-weight:bold; text-transform:uppercase; margin-bottom:12px;'>Líneas de Cierre</div>
                <div style='display:flex; justify-content:space-around; align-items:center;'>
                    <div style='text-align:center; color:#E5E5EA;'><b>{away[:3].upper()}</b><br><span style='font-size:1.6em; font-weight:900;'>{away_ml}</span></div>
                    <div style='color:#8E8E93; font-size:0.9em; font-weight:bold;'>VS</div>
                    <div style='text-align:center; color:#E5E5EA;'><b>{home[:3].upper()}</b><br><span style='font-size:1.6em; font-weight:900;'>{home_ml}</span></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        with cf2:
            st.markdown(f"""
            <div class='card-deportiva'>
                <div style='color:#8E8E93; font-size:0.85em; font-weight:bold; text-transform:uppercase; margin-bottom:12px;'>Diagnóstico Estructural</div>
                <table style='width:100%; font-size:0.95em; font-weight:600; color:#E5E5EA;'>
                    <tr><td style='padding-bottom:10px;'>Calibración</td><td style='text-align:right;'><span class='badge-blue'>Isotónica activa</span></td></tr>
                    <tr><td style='padding-bottom:10px;'>Volumen M.C.</td><td style='text-align:right;'>10,000 rondas</td></tr>
                    <tr><td style='padding-bottom:10px;'>Filtro de Ruido</td><td style='text-align:right;'><span class='badge-blue'>Activado</span></td></tr>
                </table>
            </div>
            """, unsafe_allow_html=True)

        # --- SECCIÓN DEL TRACK RECORD (ESTADÍSTICAS) ---
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
            
            if st.button("Actualizar Historial", use_container_width=True):
                tracker.update_tracker(edited_df)
                st.success("Base de datos actualizada correctamente. Recarga la página para ver tu nuevo Win Rate.")
        else:
            st.info("Aún no tienes operaciones. Cuando el modelo detecte un Edge positivo, guárdalo aquí.")