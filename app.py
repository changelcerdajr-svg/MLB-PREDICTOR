# app.py — MLB Quant Engine V17.3 (Refactored)
import streamlit as st
import datetime
import json
import pandas as pd
import numpy as np
from model import MLBPredictor
from financial import american_to_prob
import tracker

# ─── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MLB Quant Engine",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CONSTANTS ────────────────────────────────────────────────────────────────
CONFIDENCE_THRESHOLD = 0.55
MAX_ODDS_LIMIT = -250
KELLY_FRACTION = 0.25

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
}

/* ── LAYOUT ── */
section[data-testid="stSidebar"] {
    background: #0A0A0F;
    border-right: 1px solid #1E1E2E;
}
.main { background: #0D0D17; }
.block-container { padding: 1.5rem 2rem; max-width: 100%; }

/* ── SIDEBAR GAME CARDS ── */
.game-card {
    background: #131320;
    border: 1px solid #1E1E2E;
    border-radius: 10px;
    padding: 11px 14px;
    margin-bottom: 8px;
    cursor: pointer;
    transition: border-color .15s, background .15s;
}
.game-card:hover { border-color: #3B82F6; background: #161628; }
.game-card.selected { border-color: #3B82F6; background: #0F1A30; }
.game-card.final { border-color: #1E2E1E; }
.game-matchup { font-size: .82em; font-weight: 600; color: #C9C9E0; letter-spacing: .01em; }
.game-meta { font-size: .72em; color: #5A5A7A; margin-top: 3px; font-family: 'IBM Plex Mono', monospace; }

/* ── STATUS BADGES ── */
.badge {
    display: inline-block;
    font-size: .68em;
    font-weight: 700;
    font-family: 'IBM Plex Mono', monospace;
    padding: 2px 8px;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: .06em;
}
.badge-live { background: #2D1515; color: #FF4545; border: 1px solid #FF454530; }
.badge-final { background: #1A1A2A; color: #5A5A7A; border: 1px solid #2A2A3A; }
.badge-sched { background: #0F1E30; color: #3B82F6; border: 1px solid #3B82F620; }
.badge-signal { background: #0D2215; color: #22C55E; border: 1px solid #22C55E30; }
.badge-warn { background: #2A1F05; color: #F59E0B; border: 1px solid #F59E0B30; }
.badge-block { background: #200D0D; color: #FF4545; border: 1px solid #FF454520; }

/* ── PANEL CARDS ── */
.panel {
    background: #101018;
    border: 1px solid #1E1E2E;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
}
.panel-title {
    font-size: .7em;
    font-weight: 700;
    font-family: 'IBM Plex Mono', monospace;
    color: #5A5A7A;
    text-transform: uppercase;
    letter-spacing: .1em;
    margin-bottom: 14px;
}

/* ── TEAM DISPLAY ── */
.team-block { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; }
.team-block + .team-block { border-top: 1px solid #1A1A28; }
.team-name-lg { font-size: 1.1em; font-weight: 600; color: #E8E8F8; }
.team-name-lg.pick { color: #22C55E; }
.team-score { font-family: 'IBM Plex Mono', monospace; font-size: 1.4em; font-weight: 600; color: #3B82F6; }
.team-prob { font-family: 'IBM Plex Mono', monospace; font-size: .85em; color: #9090B0; }

/* ── PROB BAR ── */
.prob-bar-wrap { height: 4px; background: #1E1E2E; border-radius: 2px; margin: 14px 0 6px; overflow: hidden; }
.prob-bar-fill { height: 100%; border-radius: 2px; background: #22C55E; }

/* ── STAT TABLE ── */
.stat-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 7px 0;
    border-bottom: 1px solid #1A1A28;
    font-size: .85em;
}
.stat-row:last-child { border-bottom: none; }
.stat-label { color: #5A5A7A; font-family: 'IBM Plex Mono', monospace; font-size: .9em; }
.stat-val { color: #C9C9E0; font-weight: 600; font-family: 'IBM Plex Mono', monospace; }
.stat-val.green { color: #22C55E; }
.stat-val.blue { color: #3B82F6; }
.stat-val.amber { color: #F59E0B; }
.stat-val.red { color: #FF4545; }

/* ── KELLY BOX ── */
.kelly-box {
    background: #0A1F12;
    border: 1px solid #22C55E30;
    border-left: 3px solid #22C55E;
    border-radius: 8px;
    padding: 14px 16px;
    margin-top: 14px;
}
.kelly-box-blocked {
    background: #1A0A0A;
    border: 1px solid #FF454520;
    border-left: 3px solid #FF4545;
    border-radius: 8px;
    padding: 14px 16px;
    margin-top: 14px;
}
.kelly-amount { font-size: 1.6em; font-weight: 700; font-family: 'IBM Plex Mono', monospace; color: #22C55E; }
.kelly-label { font-size: .72em; color: #5A9A6A; text-transform: uppercase; letter-spacing: .08em; }

/* ── METRICS ── */
.metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
.metric-card { background: #101018; border: 1px solid #1E1E2E; border-radius: 10px; padding: 14px 18px; }
.metric-value { font-size: 1.5em; font-weight: 700; font-family: 'IBM Plex Mono', monospace; color: #E8E8F8; margin: 4px 0 2px; }
.metric-label { font-size: .7em; color: #5A5A7A; text-transform: uppercase; letter-spacing: .08em; }
.metric-delta { font-size: .8em; font-family: 'IBM Plex Mono', monospace; margin-top: 2px; }

/* ── EMPTY STATE ── */
.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: #3A3A5A;
}
.empty-icon { font-size: 3em; margin-bottom: 16px; opacity: .4; }
.empty-text { font-size: .9em; }

/* ── HEADER ── */
.app-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid #1A1A28;
}
.app-title { font-size: 1.4em; font-weight: 700; color: #E8E8F8; letter-spacing: -.02em; }
.app-subtitle { font-size: .75em; color: #3B82F6; font-family: 'IBM Plex Mono', monospace; margin-top: 3px; }
.app-date { font-family: 'IBM Plex Mono', monospace; font-size: .8em; color: #5A5A7A; text-align: right; }
</style>
""", unsafe_allow_html=True)

# ─── SESSION STATE ─────────────────────────────────────────────────────────────
if 'target_date' not in st.session_state:
    st.session_state.target_date = datetime.date.today()
if 'selected_game_id' not in st.session_state:
    st.session_state.selected_game_id = None
if 'analysis_cache' not in st.session_state:
    st.session_state.analysis_cache = {}

# ─── HELPERS ──────────────────────────────────────────────────────────────────
@st.cache_resource
def get_predictor():
    return MLBPredictor(use_calibrator=True)  # BUG FIX: era False

@st.cache_data(ttl=120)
def load_live_odds():
    try:
        with open('data_odds/live_odds.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def american_to_decimal(american):
    if american > 0: return (american / 100) + 1
    return (100 / abs(american)) + 1

def fmt_odds(american):
    if american is None: return "N/A"
    return f"+{american}" if american > 0 else str(american)

def calculate_kelly(prob_win, american_odds):
    if american_odds is None: return 0
    b = american_to_decimal(american_odds) - 1
    q = 1 - prob_win
    f_star = (b * prob_win - q) / b
    return max(0, f_star * KELLY_FRACTION)

def get_target_odds(odds_data, date_str, mlb_home_name):
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

def status_badge(status):
    if status in ['Live', 'In Progress']:
        return "<span class='badge badge-live'>En Vivo</span>"
    if status == 'Final':
        return "<span class='badge badge-final'>Final</span>"
    return "<span class='badge badge-sched'>Programado</span>"

def safe_edge_mean(df):
    """BUG FIX: Edge puede ser float o string con formato '+3.45%'"""
    try:
        col = pd.to_numeric(df['Edge'], errors='coerce')
        return col.mean()
    except Exception:
        return 0.0

# ─── INIT ─────────────────────────────────────────────────────────────────────
predictor = get_predictor()
odds_data = load_live_odds()

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    # Capital
    st.markdown("""
    <div style='font-size:.7em; font-weight:700; font-family:"IBM Plex Mono",monospace;
                color:#5A5A7A; text-transform:uppercase; letter-spacing:.1em; margin-bottom:10px;'>
        Capital Operativo
    </div>
    """, unsafe_allow_html=True)
    bankroll = st.number_input("Bankroll ($)", value=1000.0, step=100.0,
                               format="%.2f", label_visibility="collapsed")
    st.markdown(f"""
    <div style='font-family:"IBM Plex Mono",monospace; font-size:.75em; color:#3B82F6; margin-bottom:18px;'>
        Kelly máximo: ${bankroll * 0.05:.2f} / apuesta
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<hr style='border-color:#1E1E2E; margin:6px 0 14px;'>", unsafe_allow_html=True)

    # Date nav
    st.markdown("""
    <div style='font-size:.7em; font-weight:700; font-family:"IBM Plex Mono",monospace;
                color:#5A5A7A; text-transform:uppercase; letter-spacing:.1em; margin-bottom:10px;'>
        Navegación
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    if c1.button("◀", use_container_width=True):
        st.session_state.target_date -= datetime.timedelta(days=1)
        st.session_state.selected_game_id = None
        st.session_state.analysis_cache = {}
    if c2.button("Hoy", use_container_width=True):
        st.session_state.target_date = datetime.date.today()
        st.session_state.selected_game_id = None
        st.session_state.analysis_cache = {}
    if c3.button("▶", use_container_width=True):
        st.session_state.target_date += datetime.timedelta(days=1)
        st.session_state.selected_game_id = None
        st.session_state.analysis_cache = {}

    st.session_state.target_date = st.date_input(
        "Fecha", st.session_state.target_date, label_visibility="collapsed"
    )
    target_date_str = st.session_state.target_date.strftime("%Y-%m-%d")

    st.markdown("<hr style='border-color:#1E1E2E; margin:14px 0;'>", unsafe_allow_html=True)

    # Load games
    with st.spinner("Cargando pizarra..."):
        games = predictor.loader.get_schedule(target_date_str)

    # Game feed
    live_games = [g for g in games if g['status'] in ['Live', 'In Progress']]
    finished  = [g for g in games if g['status'] in ['Final', 'Game Over', 'Completed']]
    scheduled = [g for g in games if g['status'] not in ['Final', 'Game Over', 'Completed', 'Live', 'In Progress']]

    st.markdown(f"""
    <div style='font-size:.7em; font-weight:700; font-family:"IBM Plex Mono",monospace;
                color:#5A5A7A; text-transform:uppercase; letter-spacing:.1em; margin-bottom:10px;'>
        Pizarra — {len(games)} juegos
    </div>
    """, unsafe_allow_html=True)

    if not games:
        st.markdown("<div style='color:#3A3A5A; font-size:.82em; padding:8px;'>Sin juegos en esta fecha.</div>", unsafe_allow_html=True)
    else:
        for g in (live_games + scheduled + finished):
            game_id = g['id']
            is_selected = (st.session_state.selected_game_id == game_id)
            card_class = "game-card selected" if is_selected else ("game-card final" if g['status'] in ['Final', 'Game Over', 'Completed'] else "game-card")
            badge_html = status_badge(g['status'])

            result_str = ""
            if g.get('real_winner'):
                result_str = f" · <span style='color:#22C55E;'>{g['real_winner']}</span>"

            h_odds, a_odds = get_target_odds(odds_data, target_date_str, g['home_name'])
            odds_str = f"DK: {fmt_odds(h_odds)}/{fmt_odds(a_odds)}" if h_odds else "Sin momios"

            st.markdown(f"""
            <div class='{card_class}'>
                <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;'>
                    {badge_html}
                    <span style='font-size:.68em; font-family:"IBM Plex Mono",monospace; color:#3A3A5A;'>{odds_str}</span>
                </div>
                <div class='game-matchup'>{g['away_name']} <span style='color:#3A3A5A;'>@</span> {g['home_name']}{result_str}</div>
            </div>
            """, unsafe_allow_html=True)

            btn_label = "✓ Seleccionado" if is_selected else "Analizar"
            if g['status'] not in ['Final', 'Game Over', 'Completed']:
                if st.button(btn_label, key=f"sel_{game_id}", use_container_width=True):
                    st.session_state.selected_game_id = game_id
                    st.rerun()
            else:
                if st.button("Ver análisis", key=f"sel_{game_id}", use_container_width=True):
                    st.session_state.selected_game_id = game_id
                    st.rerun()

# ─── MAIN PANEL ───────────────────────────────────────────────────────────────
# Header
now = datetime.datetime.now()
st.markdown(f"""
<div class='app-header'>
    <div>
        <div class='app-title'>⚾ MLB Quant Engine</div>
        <div class='app-subtitle'>V17.3 · Statcast + Monte Carlo · Kelly Criterion</div>
    </div>
    <div class='app-date'>
        {st.session_state.target_date.strftime("%A, %d %b %Y")}<br>
        <span style='color:#3A3A5A;'>Actualizado {now.strftime("%H:%M")}</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Tabs
tab_pizarra, tab_tracker = st.tabs(["Panel de Inversión", "Track Record"])

# ─── TAB 1: PIZARRA ───────────────────────────────────────────────────────────
with tab_pizarra:
    selected_game = None
    if st.session_state.selected_game_id:
        selected_game = next(
            (g for g in games if g['id'] == st.session_state.selected_game_id), None
        )

    if not games:
        st.markdown("""
        <div class='empty-state'>
            <div class='empty-icon'>⚾</div>
            <div class='empty-text'>Sin juegos para esta fecha.<br>Navega el calendario en el panel izquierdo.</div>
        </div>
        """, unsafe_allow_html=True)

    elif selected_game is None:
        # ── OVERVIEW cuando no hay juego seleccionado ──
        n_sched = len(scheduled) + len(live_games)
        n_odds  = sum(1 for g in games if get_target_odds(odds_data, target_date_str, g['home_name'])[0] is not None)

        st.markdown(f"""
        <div class='metric-grid'>
            <div class='metric-card'>
                <div class='metric-label'>Juegos hoy</div>
                <div class='metric-value'>{len(games)}</div>
                <div class='metric-delta' style='color:#5A5A7A;'>{n_sched} por jugar</div>
            </div>
            <div class='metric-card'>
                <div class='metric-label'>Con momios DK</div>
                <div class='metric-value' style='color:#3B82F6;'>{n_odds}</div>
                <div class='metric-delta' style='color:#5A5A7A;'>de {len(games)} total</div>
            </div>
            <div class='metric-card'>
                <div class='metric-label'>Umbral confianza</div>
                <div class='metric-value' style='color:#F59E0B;'>{int(CONFIDENCE_THRESHOLD*100)}%</div>
                <div class='metric-delta' style='color:#5A5A7A;'>Filtro activo</div>
            </div>
            <div class='metric-card'>
                <div class='metric-label'>Kelly fracción</div>
                <div class='metric-value' style='color:#22C55E;'>¼</div>
                <div class='metric-delta' style='color:#5A5A7A;'>Protección varianza</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class='empty-state' style='padding:40px 20px;'>
            <div class='empty-icon'>←</div>
            <div class='empty-text'>Selecciona un juego en el panel izquierdo<br>para ver el análisis cuantitativo completo.</div>
        </div>
        """, unsafe_allow_html=True)

    else:
        # ── ANÁLISIS DEL JUEGO SELECCIONADO ──
        g = selected_game
        game_id = g['id']

        # Cache del análisis — no re-calcular si ya existe
        if game_id not in st.session_state.analysis_cache:
            with st.spinner(f"Corriendo 10,000 simulaciones Monte Carlo..."):
                res = predictor.predict_game(g)
            st.session_state.analysis_cache[game_id] = res
        else:
            res = st.session_state.analysis_cache[game_id]

        h_odds, a_odds = get_target_odds(odds_data, target_date_str, g['home_name'])

        # ── GAME HEADER ──
        is_final = g['status'] in ['Final', 'Game Over', 'Completed']
        badge_h = status_badge(g['status'])
        result_note = ""
        if is_final and g.get('real_winner'):
            result_note = f"<span style='color:#22C55E; font-size:.9em;'>· Resultado: {g['real_winner']}</span>"

        st.markdown(f"""
        <div style='margin-bottom:20px;'>
            <div style='display:flex; align-items:center; gap:10px; margin-bottom:6px;'>
                {badge_h} {result_note}
            </div>
            <div style='font-size:1.25em; font-weight:700; color:#E8E8F8; letter-spacing:-.02em;'>
                {g['away_name']} <span style='color:#3A3A5A;'>@</span> {g['home_name']}
            </div>
        </div>
        """, unsafe_allow_html=True)

        if 'error' in res:
            st.error(f"Datos insuficientes: {res['error']}")
            st.info("El modelo requiere lineups confirmados y abridores con historial Statcast.")
        else:
            prob_home = res['home_prob']
            prob_away = res['away_prob']
            pick = res['winner']
            conf = res['confidence']
            details = res.get('details', {})

            col_left, col_right = st.columns([3, 2], gap="large")

            with col_left:
                st.markdown("<div class='panel'><div class='panel-title'>Simulación Monte Carlo — Probabilidades</div>", unsafe_allow_html=True)

                is_pick_away = (pick == g['away_name'])
                name_class_a = "team-name-lg pick" if is_pick_away else "team-name-lg"
                pick_badge_a = "<span style='font-size:.65em; color:#22C55E; margin-left:8px;'>← PICK</span>" if is_pick_away else ""
                
                # Sin sangría izquierda para evitar el renderizado de bloque de código
                st.markdown(f"""
<div class='team-block'>
    <div>
        <div class='{name_class_a}'>{g['away_name']}{pick_badge_a}</div>
        <div style='font-family:"IBM Plex Mono",monospace; font-size:.75em; color:#5A5A7A; margin-top:2px;'>Visitante · xwOBA lineup</div>
    </div>
    <div style='text-align:right;'>
        <div class='team-score'>{res['score']['away']:.1f}</div>
        <div class='team-prob'>{prob_away*100:.1f}%</div>
    </div>
</div>
""", unsafe_allow_html=True)

                fill_pct = prob_home * 100
                st.markdown(f"""
<div class='prob-bar-wrap'>
    <div class='prob-bar-fill' style='width:{fill_pct:.1f}%; background: linear-gradient(90deg, #22C55E, #3B82F6);'></div>
</div>
<div style='display:flex; justify-content:space-between; font-family:"IBM Plex Mono",monospace; font-size:.7em; color:#3A3A5A; margin-bottom:4px;'>
    <span>{prob_away*100:.1f}%</span>
    <span>Total proyectado: {res['score']['total']:.1f} carreras</span>
    <span>{prob_home*100:.1f}%</span>
</div>
""", unsafe_allow_html=True)

                is_pick_home = (pick == g['home_name'])
                name_class_h = "team-name-lg pick" if is_pick_home else "team-name-lg"
                pick_badge_h = "<span style='font-size:.65em; color:#22C55E; margin-left:8px;'>← PICK</span>" if is_pick_home else ""
                
                st.markdown(f"""
<div class='team-block'>
    <div>
        <div class='{name_class_h}'>{g['home_name']}{pick_badge_h}</div>
        <div style='font-family:"IBM Plex Mono",monospace; font-size:.75em; color:#5A5A7A; margin-top:2px;'>Local · xERA abridor</div>
    </div>
    <div style='text-align:right;'>
        <div class='team-score'>{res['score']['home']:.1f}</div>
        <div class='team-prob'>{prob_home*100:.1f}%</div>
    </div>
</div>
</div>
""", unsafe_allow_html=True)

                st.markdown("<div class='panel'><div class='panel-title'>Diagnóstico Cuantitativo</div>", unsafe_allow_html=True)

                pitch_txt = details.get('pitching', 'N/A')
                fat_txt   = details.get('fatigue',  'N/A')
                env_txt   = details.get('league_env','N/A')
                lineup_txt= details.get('lineup',   'N/A')
                sens_txt  = details.get('sensitivity','N/A')
                key_txt   = res.get('key_factor', 'N/A')

                raw_sens = res.get('raw_sensitivity', 0)
                sens_color = "red" if raw_sens > 0.045 else ("amber" if raw_sens > 0.025 else "green")

                st.markdown(f"""
<div class='stat-row'>
    <span class='stat-label'>Pitcheo (xERA)</span>
    <span class='stat-val'>{pitch_txt}</span>
</div>
<div class='stat-row'>
    <span class='stat-label'>Fatiga Bullpen</span>
    <span class='stat-val'>{fat_txt}</span>
</div>
<div class='stat-row'>
    <span class='stat-label'>Entorno Liga</span>
    <span class='stat-val blue'>{env_txt}</span>
</div>
<div class='stat-row'>
    <span class='stat-label'>Lineups</span>
    <span class='stat-val {"green" if lineup_txt == "CONFIRMADO" else "amber"}'>{lineup_txt}</span>
</div>
<div class='stat-row'>
    <span class='stat-label'>Sensibilidad</span>
    <span class='stat-val {sens_color}'>{sens_txt}</span>
</div>
<div class='stat-row'>
    <span class='stat-label'>Factor Clave</span>
    <span class='stat-val' style='font-size:.8em;'>{key_txt}</span>
</div>
</div>
""", unsafe_allow_html=True)

            with col_right:
                st.markdown("<div class='panel'><div class='panel-title'>Análisis de Mercado — DraftKings</div>", unsafe_allow_html=True)

                if h_odds is None:
                    st.markdown("""
<div style='text-align:center; padding:24px; color:#3A3A5A;'>
    <div style='font-size:1.5em; margin-bottom:8px;'>⏳</div>
    <div style='font-size:.82em;'>Momios no disponibles.<br>Corre live_odds_scraper.py</div>
</div>
""", unsafe_allow_html=True)
                else:
                    curr_odds = h_odds if pick == g['home_name'] else a_odds
                    mkt_prob  = american_to_prob(curr_odds)
                    edge      = conf - mkt_prob

                    sig_badge = "<span class='badge badge-signal'>Señal Activa</span>" if conf >= CONFIDENCE_THRESHOLD else "<span class='badge badge-warn'>Baja Confianza</span>"

                    st.markdown(f"""
<div style='margin-bottom:14px;'>{sig_badge}</div>
<div class='stat-row'>
    <span class='stat-label'>Pick</span>
    <span class='stat-val green'>{pick}</span>
</div>
<div class='stat-row'>
    <span class='stat-label'>Momio {pick.split()[-1]}</span>
    <span class='stat-val'>{fmt_odds(curr_odds)}</span>
</div>
<div class='stat-row'>
    <span class='stat-label'>Prob. Modelo</span>
    <span class='stat-val green'>{conf*100:.1f}%</span>
</div>
<div class='stat-row'>
    <span class='stat-label'>Prob. Mercado</span>
    <span class='stat-val'>{mkt_prob*100:.1f}%</span>
</div>
<div class='stat-row'>
    <span class='stat-label'>Edge</span>
    <span class='stat-val {"green" if edge > 0 else "red"}'>{edge*100:+.2f}%</span>
</div>
""", unsafe_allow_html=True)

                    odds_ok = (curr_odds is not None) and (curr_odds >= 0 or curr_odds >= MAX_ODDS_LIMIT)
                    can_bet = conf >= CONFIDENCE_THRESHOLD and odds_ok

                    if can_bet:
                        stake_pct = calculate_kelly(conf, curr_odds)
                        if stake_pct > 0:
                            stake_amount = bankroll * stake_pct
                            st.markdown(f"""
<div class='kelly-box'>
    <div class='kelly-label'>Inversión Recomendada (¼ Kelly)</div>
    <div class='kelly-amount'>${stake_amount:.2f}</div>
    <div style='font-size:.75em; color:#5A9A6A; font-family:"IBM Plex Mono",monospace; margin-top:4px;'>
        {stake_pct*100:.2f}% del bankroll
    </div>
</div>
""", unsafe_allow_html=True)
                        else:
                            st.markdown("<div class='kelly-box-blocked'><span style='color:#FF4545; font-weight:600; font-size:.85em;'>EDGE NEGATIVO — Mercado eficiente</span></div>", unsafe_allow_html=True)
                    elif not odds_ok:
                        st.markdown(f"<div class='kelly-box-blocked'><span style='color:#FF4545; font-weight:600; font-size:.85em;'>LÍMITE EXPOSICIÓN — Momio {curr_odds} excede {MAX_ODDS_LIMIT}</span></div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='kelly-box-blocked'><span style='color:#F59E0B; font-weight:600; font-size:.85em;'>CONFIANZA INSUFICIENTE — Requiere ≥{int(CONFIDENCE_THRESHOLD*100)}%</span></div>", unsafe_allow_html=True)

                st.markdown("</div>", unsafe_allow_html=True)

                # ── REGISTRAR OPERACIÓN ──
                if h_odds is not None and can_bet and stake_pct > 0:
                    st.markdown("<div style='margin-top:12px;'>", unsafe_allow_html=True)
                    btn_key = f"reg_{g['home_name'].replace(' ', '_')}_{target_date_str}"
                    if st.button("Registrar en Bitácora", key=btn_key, use_container_width=True, type="primary"):
                        saved = tracker.log_bet(
                            fecha=target_date_str,
                            juego=f"{g['away_name']} @ {g['home_name']}",
                            pick=pick,
                            confianza=round(conf * 100, 1),
                            prob_mercado=mkt_prob,
                            cuota=curr_odds,
                            edge=round(edge * 100, 2)
                        )
                        if saved:
                            st.success("Operación guardada en history_log.csv")
                        else:
                            st.warning("Ya estaba registrada para este juego.")
                    st.markdown("</div>", unsafe_allow_html=True)

# ─── TAB 2: TRACK RECORD ──────────────────────────────────────────────────────
with tab_tracker:
    try:
        df_log = tracker.load_tracker()
        if df_log.empty:
            st.markdown("""
            <div class='empty-state'>
                <div class='empty-icon'>📊</div>
                <div class='empty-text'>La bitácora está vacía.<br>Registra tu primera operación desde el Panel de Inversión.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            df_log['Fecha'] = pd.to_datetime(df_log['Fecha'])
            df_log = df_log.sort_values(by='Fecha', ascending=False).reset_index(drop=True)

            # Métricas
            ganados    = len(df_log[df_log['Resultado'] == 'Ganado'])
            perdidos   = len(df_log[df_log['Resultado'] == 'Perdido'])
            pendientes = len(df_log[df_log['Resultado'] == 'Pendiente'])
            total_cerr = ganados + perdidos
            win_rate   = (ganados / total_cerr * 100) if total_cerr > 0 else 0.0

            # BUG FIX: ROI real calculado correctamente
            roi = 0.0
            if total_cerr > 0:
                # Cuota puede ser int (american odds) — calculamos payout real
                def calc_pnl(row):
                    try:
                        odds = float(row['Cuota'])
                        if row['Resultado'] == 'Ganado':
                            return (odds / 100) if odds > 0 else (100 / abs(odds))
                        elif row['Resultado'] == 'Perdido':
                            return -1.0
                        return 0.0
                    except Exception:
                        return 0.0

                df_closed = df_log[df_log['Resultado'].isin(['Ganado', 'Perdido'])].copy()
                df_closed['pnl'] = df_closed.apply(calc_pnl, axis=1)
                total_pnl = df_closed['pnl'].sum()
                roi = (total_pnl / total_cerr) * 100

            edge_avg = safe_edge_mean(df_log)
            conf_avg = df_log['Confianza (%)'].mean() if 'Confianza (%)' in df_log.columns else 0

            st.markdown(f"""
            <div class='metric-grid'>
                <div class='metric-card'>
                    <div class='metric-label'>Win Rate</div>
                    <div class='metric-value' style='color:{"#22C55E" if win_rate >= 55 else "#F59E0B"};'>{win_rate:.1f}%</div>
                    <div class='metric-delta' style='color:#5A5A7A;'>{ganados}G · {perdidos}P · {pendientes} pend.</div>
                </div>
                <div class='metric-card'>
                    <div class='metric-label'>ROI Real</div>
                    <div class='metric-value' style='color:{"#22C55E" if roi >= 0 else "#FF4545"};'>{roi:+.2f}%</div>
                    <div class='metric-delta' style='color:#5A5A7A;'>{total_cerr} operaciones cerradas</div>
                </div>
                <div class='metric-card'>
                    <div class='metric-label'>Confianza Media</div>
                    <div class='metric-value'>{conf_avg:.1f}%</div>
                    <div class='metric-delta' style='color:#5A5A7A;'>Umbral mín. {int(CONFIDENCE_THRESHOLD*100)}%</div>
                </div>
                <div class='metric-card'>
                    <div class='metric-label'>Edge Promedio</div>
                    <div class='metric-value' style='color:{"#22C55E" if edge_avg >= 0 else "#FF4545"};'>{edge_avg:+.2f}%</div>
                    <div class='metric-delta' style='color:#5A5A7A;'>vs. mercado sin vig</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Tabla editable
            st.markdown("<div style='margin-bottom:8px; font-size:.7em; font-family:\"IBM Plex Mono\",monospace; color:#5A5A7A; text-transform:uppercase; letter-spacing:.08em;'>Edita el resultado y presiona Guardar</div>", unsafe_allow_html=True)

            edited_df = st.data_editor(
                df_log,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Resultado": st.column_config.SelectboxColumn(
                        "Resultado",
                        options=["Pendiente", "Ganado", "Perdido"],
                        required=True
                    ),
                    "Fecha": st.column_config.DateColumn("Fecha", format="YYYY-MM-DD"),
                }
            )

            if st.button("Guardar Historial", use_container_width=True, type="primary"):
                edited_df.to_csv(tracker.FILE, index=False)
                st.success("Bitácora actualizada.")

    except Exception as e:
        st.error(f"Error cargando el tracker: {e}")