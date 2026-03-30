# app_demo.py — Quantitative Institutional Terminal (MVP)
import streamlit as st
import datetime
import json
import textwrap
import requests
from model import MLBPredictor
from financial import american_to_prob, get_fair_prob, calculate_edge

# --- CONFIGURATION ---
st.set_page_config(page_title="MLB Quant Terminal", layout="wide", initial_sidebar_state="expanded")

# --- CSS STYLING ---
css = textwrap.dedent("""
<style>
    .stApp { background-color: #0A0A0F; color: #FFFFFF; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
    [data-testid="stSidebar"] { background-color: #12121A !important; border-right: 1px solid #1E1E2E; }
    
    /* Sidebar Navigation */
    .nav-btn { display: inline-block; width: 100%; text-align: center; padding: 10px; background: #1A1A24; border: 1px solid #2A2A3A; border-radius: 6px; color: #8C8E96; text-decoration: none; font-weight: 600; font-size: 0.85em; cursor: pointer; text-transform: uppercase; letter-spacing: 1px; }
    .nav-btn:hover { background: #222230; color: #FFFFFF; }
    
    /* Game Cards */
    .game-box { background: #161622; border: 1px solid #2A2A3A; border-radius: 8px; padding: 12px; margin-bottom: 10px; cursor: pointer; transition: 0.2s; }
    .game-box:hover { border-color: #3B82F6; }
    .game-box.active { border-color: #3B82F6; background: #3B82F615; border-left: 4px solid #3B82F6; }
    .team-abrv { font-size: 1.1em; font-weight: 700; color: #EAEAEA; display: flex; align-items: center; gap: 8px; }
    .game-time { font-size: 0.7em; color: #8C8E96; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
    .logo-micro { height: 16px; width: 16px; object-fit: contain; }
    
    /* Main Panel */
    .main-card { background: #161622; border: 1px solid #2A2A3A; border-radius: 12px; padding: 30px; margin-top: 10px; }
    .matchup-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #2A2A3A; padding-bottom: 20px; margin-bottom: 24px; }
    .team-display { display: flex; align-items: center; gap: 15px; }
    .logo-large { height: 50px; width: 50px; object-fit: contain; }
    .team-name-big { font-size: 1.8em; font-weight: 800; letter-spacing: -0.5px; line-height: 1.1; }
    .pitcher-sub { font-size: 0.85em; color: #8C8E96; font-weight: 500; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
    
    /* Edge Visualizer */
    .edge-bar-container { width: 100%; background: #1A1A24; border-radius: 6px; height: 12px; margin: 15px 0; overflow: hidden; display: flex; border: 1px solid #2A2A3A; }
    .edge-bar-market { height: 100%; background: #3A3A4A; }
    .edge-bar-alpha { height: 100%; background: #00D26A; }
    
    /* Data Grid */
    .data-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-bottom: 20px; }
    .data-block { background: #0A0A0F; border: 1px solid #2A2A3A; border-radius: 8px; padding: 16px; text-align: center; }
    .data-label { font-size: 0.7em; color: #8C8E96; text-transform: uppercase; letter-spacing: 1px; font-weight: 700; margin-bottom: 6px; }
    .data-value { font-size: 1.6em; font-weight: 800; }
    
    /* Colors & Badges */
    .text-blue { color: #3B82F6; }
    .text-green { color: #00D26A; }
    .text-red { color: #FF3B30; }
    .badge { display: inline-block; padding: 4px 10px; border-radius: 4px; font-size: 0.7em; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; }
    .badge-a { background: #00D26A20; color: #00D26A; border: 1px solid #00D26A; }
    .badge-b { background: #3B82F620; color: #3B82F6; border: 1px solid #3B82F6; }
    .badge-c { background: #F59E0B20; color: #F59E0B; border: 1px solid #F59E0B; }
    .badge-no { background: #FF3B3020; color: #FF3B30; border: 1px solid #FF3B30; }
    
    /* Investment Box */
    .invest-box { background: #0D1712; border: 1px solid #00D26A50; border-left: 4px solid #00D26A; border-radius: 8px; padding: 20px; margin-top: 20px; display: flex; justify-content: space-between; align-items: center; }
    .invest-box.blocked { background: #1A0D0D; border-color: #FF3B3050; border-left-color: #FF3B30; }
    .invest-amount { font-size: 2.2em; font-weight: 800; color: #00D26A; margin-bottom: 4px; }
    
    /* Dashboard Specific */
    .dash-metric { background: #161622; border: 1px solid #2A2A3A; border-radius: 8px; padding: 20px; }
</style>
""")
st.markdown(css, unsafe_allow_html=True)

# --- STATE MANAGEMENT ---
if 'demo_date' not in st.session_state:
    st.session_state.demo_date = datetime.date.today()
if 'selected_game' not in st.session_state:
    st.session_state.selected_game = None
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = 'terminal'

# --- DATA HELPERS ---
@st.cache_resource
def get_predictor(): return MLBPredictor(use_calibrator=True)

@st.cache_data(ttl=60)
def load_live_odds():
    try:
        with open('data_odds/live_odds.json', 'r') as f: return json.load(f)
    except: return {}

@st.cache_data(ttl=3600)
def get_pitcher_name(pid):
    if not pid: return "TBA"
    try:
        r = requests.get(f"https://statsapi.mlb.com/api/v1/people/{pid}", timeout=3).json()
        return r['people'][0]['fullName']
    except: return f"ID: {pid}"

def get_logo_url(team_id):
    return f"https://www.mlbstatic.com/team-logos/{team_id}.svg"

def get_target_odds(odds_data, date_str, home_name):
    day_games = odds_data.get(date_str, [])
    mlb_clean = home_name.lower().strip()
    for game in day_games:
        dk_name = game.get('gameView', {}).get('homeTeam', {}).get('fullName', '').lower().strip()
        if mlb_clean in dk_name or dk_name in mlb_clean:
            ml_list = game.get('odds', {}).get('moneyline', [])
            for book in ml_list:
                if book.get('sportsbook') == 'draftkings':
                    line = book.get('currentLine')
                    if line: return line.get('homeOdds'), line.get('awayOdds')
            if ml_list and ml_list[0].get('currentLine'):
                return ml_list[0]['currentLine'].get('homeOdds'), ml_list[0]['currentLine'].get('awayOdds')
    return None, None

def calc_kelly_and_ev(prob_win, american_odds, bankroll=10000):
    if american_odds is None: return 0, 0
    b = (american_odds / 100) if american_odds > 0 else (100 / abs(american_odds))
    q = 1 - prob_win
    if b == 0: return 0, 0
    f_star = (b * prob_win - q) / b
    rec_bet = max(0, (f_star * 0.25) * bankroll)
    
    profit_if_win = rec_bet * b
    ev = (prob_win * profit_if_win) - (q * rec_bet)
    return rec_bet, ev

# --- INITIALIZATION ---
predictor = get_predictor()
odds_data = load_live_odds()
date_str = st.session_state.demo_date.strftime("%Y-%m-%d")

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("<h2 style='text-align:center; font-weight:800; letter-spacing:-1px; margin-bottom:5px;'>QUANT TERMINAL</h2>", unsafe_allow_html=True)
    
    col_v1, col_v2 = st.columns(2)
    if col_v1.button("LIVE TERMINAL", use_container_width=True):
        st.session_state.view_mode = 'terminal'
        st.rerun()
    if col_v2.button("PERFORMANCE", use_container_width=True):
        st.session_state.view_mode = 'dashboard'
        st.rerun()
        
    st.markdown("<hr style='border-color:#1E1E2E; margin: 15px 0;'>", unsafe_allow_html=True)
    
    st.markdown("<div style='font-size:0.7em; color:#8C8E96; font-weight:700; text-transform:uppercase; margin-bottom:8px;'>Schedule Navigation</div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    if col1.button("◀", use_container_width=True): 
        st.session_state.demo_date -= datetime.timedelta(days=1)
        st.session_state.selected_game = None
        st.rerun()
    col2.markdown(f"<div style='text-align:center; font-weight:700; padding-top:5px; font-size:0.9em;'>{st.session_state.demo_date.strftime('%b %d, %Y')}</div>", unsafe_allow_html=True)
    if col3.button("▶", use_container_width=True): 
        st.session_state.demo_date += datetime.timedelta(days=1)
        st.session_state.selected_game = None
        st.rerun()

    st.markdown("<hr style='border-color:#1E1E2E; margin: 15px 0;'>", unsafe_allow_html=True)
    
    games = predictor.loader.get_schedule(date_str)
    
    if not games:
        st.markdown("<div style='text-align:center; color:#8C8E96; font-size:0.85em; margin-top:20px;'>No games scheduled.</div>", unsafe_allow_html=True)
    else:
        for g in games:
            is_active = "active" if st.session_state.selected_game and st.session_state.selected_game['id'] == g['id'] else ""
            h_odds, _ = get_target_odds(odds_data, date_str, g['home_name'])
            odds_display = f"DK: {h_odds}" if h_odds else "Awaiting Lines"
            a_logo = get_logo_url(g['away_id'])
            h_logo = get_logo_url(g['home_id'])
            
            st.markdown(textwrap.dedent(f"""
            <div class='game-box {is_active}'>
                <div class='game-time'>{g.get('status', 'Scheduled')} | {odds_display}</div>
                <div style='margin-top:8px; display:flex; flex-direction:column; gap:4px;'>
                    <div class='team-abrv'><img src='{a_logo}' class='logo-micro'> {g['away_name']}</div>
                    <div class='team-abrv' style='color:#8C8E96;'><img src='{h_logo}' class='logo-micro'> {g['home_name']}</div>
                </div>
            </div>
            """), unsafe_allow_html=True)
            
            if st.button(f"Analyze {g['id']}", key=g['id'], use_container_width=True):
                st.session_state.selected_game = g
                st.session_state.view_mode = 'terminal'
                st.rerun()

# --- MAIN WORKSPACE ---
if st.session_state.view_mode == 'dashboard':
    html_dash = """
    <div style='margin-bottom: 30px;'>
        <h2 style='margin:0; font-weight:800;'>PORTFOLIO PERFORMANCE</h2>
        <div style='color:#8C8E96; font-size:0.9em; text-transform:uppercase; letter-spacing:1px;'>Current Month Metrics | Base Capital: $10,000.00</div>
    </div>
    <div style='display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px;'>
        <div class='dash-metric'>
            <div class='data-label'>Total Equity</div>
            <div style='font-size: 2em; font-weight: 800; color: #00D26A;'>$11,482.50</div>
        </div>
        <div class='dash-metric'>
            <div class='data-label'>Monthly ROI</div>
            <div style='font-size: 2em; font-weight: 800; color: #00D26A;'>+14.82%</div>
        </div>
        <div class='dash-metric'>
            <div class='data-label'>Win Rate</div>
            <div style='font-size: 2em; font-weight: 800; color: #EAEAEA;'>58.6%</div>
        </div>
        <div class='dash-metric'>
            <div class='data-label'>Alpha (Edge)</div>
            <div style='font-size: 2em; font-weight: 800; color: #3B82F6;'>+6.4%</div>
        </div>
    </div>
    """
    st.markdown(html_dash, unsafe_allow_html=True)

else:
    if st.session_state.selected_game is None:
        st.markdown("<h3 style='text-align:center; color:#8C8E96; margin-top:50px;'>SELECT A MATCHUP TO START</h3>", unsafe_allow_html=True)
    else:
        g = st.session_state.selected_game
        res = predictor.predict_game(g)
        
        if 'error' in res:
            st.error(res['error'])
        else:
            # 1. Datos básicos
            h_pitcher = get_pitcher_name(g['home_pitcher'])
            a_pitcher = get_pitcher_name(g['away_pitcher'])
            h_logo, a_logo = get_logo_url(g['home_id']), get_logo_url(g['away_id'])
            
            # 2. Resultados del Modelo
            pick, prob = res['winner'], res['confidence']
            h_odds, a_odds = get_target_odds(odds_data, date_str, g['home_name'])
            
            # 3. Cálculo de Edge Institucional (Sin Vig)
            fair_h, fair_a = get_fair_prob(h_odds, a_odds) if h_odds else (0.5, 0.5)
            market_prob_clean = fair_h if pick == g['home_name'] else fair_a
            curr_odds = h_odds if pick == g['home_name'] else a_odds
            
            edge_report = calculate_edge(prob, market_prob_clean)
            edge = edge_report['edge']
            verdict = edge_report['verdict']
            kelly_fraction = edge_report['kelly'] # Consumimos el Kelly real validado

            # 4. Asignación de Grado
            if "HIGH" in verdict: grade = "<span class='badge badge-a'>GRADE A</span>"
            elif "VALUE" in verdict: grade = "<span class='badge badge-b'>GRADE B</span>"
            else: grade = "<span class='badge badge-no'>NO PLAY</span>"

            html_main = f"""
            <div class='main-card'>
                <div class='matchup-header'>
                    <div class='team-display'><img src='{a_logo}' class='logo-large'><div><div class='team-name-big'>{g['away_name']}</div><div class='pitcher-sub'>SP: {a_pitcher}</div></div></div>
                    <div style='font-weight:800; color:#3A3A4A;'>VS</div>
                    <div class='team-display' style='text-align:right;'><img src='{h_logo}' class='logo-large'><div><div class='team-name-big'>{g['home_name']}</div><div class='pitcher-sub'>SP: {h_pitcher}</div></div></div>
                </div>
                <div style='text-align:center; margin-bottom:20px;'><div class='data-label'>SELECTION</div><div style='font-size:2em; font-weight:800;'>{pick}</div></div>
                <div class='data-grid'>
                    <div class='data-block'><div class='data-label'>MODEL</div><div class='data-value text-blue'>{prob*100:.1f}%</div></div>
                    <div class='data-block'><div class='data-label'>GRADE</div><div style='margin-top:10px;'>{grade}</div></div>
                    <div class='data-block'><div class='data-label'>MARKET</div><div class='data-value'>{market_prob_clean*100:.1f}%</div></div>
                </div>
            </div>
            """
            st.markdown(html_main, unsafe_allow_html=True)

            # 5. Panel de Diagnóstico Cuantitativo (El "Por Qué")
            with st.expander("VER DIAGNÓSTICO DEL MODELO (STATCAST & MONTE CARLO)", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Métricas de Lanzadores (xERA):**")
                    st.code(res['details']['pitching'])
                    st.markdown("**Estado del Bullpen (Fatiga):**")
                    st.code(res['details']['fatigue'])
                with col2:
                    st.markdown("**Sensibilidad de Simulación:**")
                    st.code(res['details']['sensitivity'])
                    st.markdown("**Calidad del Lineup (Splits vs L/R):**")
                    st.code(res['details']['lineup'])

            # 6. Módulo de Inversión Unificado
            if curr_odds and edge > 0:
                bankroll = 10000.0 # Esto podría venir de tu tracker en el futuro
                rec_bet = bankroll * kelly_fraction
                
                # Cálculo de Valor Esperado (EV) usando matemática decimal
                b = (curr_odds / 100) if curr_odds > 0 else (100 / abs(curr_odds))
                ev = (prob * (rec_bet * b)) - ((1 - prob) * rec_bet)
                
                st.markdown(f"""
                <div class='invest-box'>
                    <div><div class='data-label'>APPROVED ALLOCATION</div><div style='font-size:1.5em; font-weight:800;'>${rec_bet:.2f}</div></div>
                    <div style='text-align:right;'><div class='data-label'>EXPECTED VALUE</div><div class='text-green' style='font-weight:800;'>+${ev:.2f}</div></div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("<div class='invest-box blocked'><div class='data-label'>ALLOCATION BLOCKED (NEGATIVE EDGE)</div></div>", unsafe_allow_html=True)