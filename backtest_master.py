# backtest_master.py
# Motor de Validación Institucional V17.9 (Vig-Killer + Alpha True)

import json
import datetime
import textwrap
from model import MLBPredictor
# PUNTO 1 AUDITORÍA: Conexión obligatoria con el motor financiero
from financial import get_fair_prob, calculate_edge, american_to_prob

# --- CONFIGURACIÓN ESTRATÉGICA ---
DATASET_PATH = 'data_odds/mlb_odds_dataset.json'
CONFIDENCE_THRESHOLD = 0.55  # Umbral de confianza del modelo
MAX_ODDS_LIMIT = -250        # Protección contra favoritos extremos
KELLY_FRACTION = 0.25        # Gestión de riesgo (1/4 Kelly)
STARTING_BANKROLL = 1000.0   # Capital inicial de simulación

def load_odds_data():
    try:
        with open(DATASET_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error cargando dataset de momios: {e}")
        return {}

def american_to_decimal(american):
    if american > 0: return (american / 100) + 1
    return (100 / abs(american)) + 1

def calculate_payout_flat(odds, stake=1.0):
    if odds > 0: return stake * (odds / 100)
    return stake * (100 / abs(odds))

def calculate_kelly_stake(prob_win, american_odds):
    b = american_to_decimal(american_odds) - 1
    q = 1 - prob_win
    f_star = (b * prob_win - q) / b
    return max(0, f_star * KELLY_FRACTION)

def get_real_odds(odds_data, date_str, mlb_home_name):
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

def run_master_backtest(start_date_str, days=45):
    # use_calibrator=False para medir el Alpha puro del motor
    predictor = MLBPredictor(use_calibrator=False) 
    odds_data = load_odds_data()
    start_dt = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
    
    bankroll = STARTING_BANKROLL
    stats = {
        'total_games': 0, 'bets': 0, 'won': 0, 
        'flat_profit': 0.0, 'baseline_home_wins': 0,
        'total_real_edge': 0.0
    }

    print("=" * 70)
    print(f"🚀 INICIANDO BACKTEST MASTER V17.9: {start_date_str} (+{days} días)")
    print(f"Lógica: Vig-Killer Activo | Talento Calibrado (0.885) | Alpha Real")
    print("=" * 70)
    
    for i in range(days):
        date_str = (start_dt + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        games = predictor.loader.get_schedule(date_str)
        
        for g in games:
            if g['status'] != 'Final': continue
            stats['total_games'] += 1
            if g['real_winner'] == g['home_name']: stats['baseline_home_wins'] += 1
                
            h_odds, a_odds = get_real_odds(odds_data, date_str, g['home_name'])
            if h_odds is None or a_odds is None: continue
            
            res = predictor.predict_game(g)
            if 'error' in res: continue
            
            prob = res['confidence']
            pick, winner = res['winner'], g['real_winner']
            curr_odds = h_odds if pick == g['home_name'] else a_odds

            # --- CIRUGÍA DE EMERGENCIA V17.9: EL VIG-KILLER ---
            
            # 1. Eliminación del Margen (Fair Value)
            fair_h, fair_a = get_fair_prob(h_odds, a_odds)
            market_prob_clean = fair_h if pick == g['home_name'] else fair_a
            
            # 2. Cálculo del Edge Real (Alpha True)
            edge_report = calculate_edge(prob, market_prob_clean)
            real_edge = edge_report['edge']
            
            # 3. FILTROS DE AUDITORÍA
            if prob < CONFIDENCE_THRESHOLD: continue
            if curr_odds < 0 and curr_odds < MAX_ODDS_LIMIT: continue
            
            # BLOQUEO CRÍTICO: Si no hay ventaja sobre el valor justo, no hay apuesta
            if real_edge <= 0:
                continue 
            # -----------------------------------------------------------------------

            # Gestión de Capital (Kelly sobre Momio Real)
            stake_pct = calculate_kelly_stake(prob, curr_odds)
            if stake_pct <= 0: continue
            
            stake_units = bankroll * stake_pct
            stats['bets'] += 1
            stats['total_real_edge'] += real_edge
            
            if pick == winner:
                stats['won'] += 1
                stats['flat_profit'] += calculate_payout_flat(curr_odds)
                kelly_gain = stake_units * (american_to_decimal(curr_odds) - 1)
                bankroll += kelly_gain
                print(f"✅ {date_str} | {pick:15} | Edge: {real_edge*100:+.1f}% | +${kelly_gain:.2f}")
            else:
                stats['flat_profit'] -= 1.0
                bankroll -= stake_units
                print(f"❌ {date_str} | {pick:15} | Edge: {real_edge*100:+.1f}% | -${stake_units:.2f}")

    # --- REPORTE DE ALPHA REAL ---
    print("\n" + "=" * 70)
    print("📊 RESULTADOS FINALES (POST-VIG & CALIBRATED)")
    print("=" * 70)
    
    if stats['bets'] > 0:
        win_rate = (stats['won'] / stats['bets']) * 100
        kelly_growth = ((bankroll - STARTING_BANKROLL) / STARTING_BANKROLL) * 100
        avg_edge = (stats['total_real_edge'] / stats['bets']) * 100
        
        print(f"Muestra Operativa:    {stats['bets']} apuestas de {stats['total_games']} juegos")
        print(f"Precisión Real:       {win_rate:.2f}%")
        print(f"Alpha Promedio:       {avg_edge:+.2f}% (Ventaja sobre Fair Value)")
        print("-" * 70)
        print(f"ROI FLAT (1u):        {(stats['flat_profit']/stats['bets'])*100:+.2f}%")
        print(f"CRECIMIENTO KELLY:    {kelly_growth:+.2f}% (Final: ${bankroll:.2f})")
    else:
        print("El modelo no encontró valor real tras eliminar la comisión del casino.")
    print("=" * 70)

if __name__ == "__main__":
    # Prueba sobre el dataset de agosto de 2025
    run_master_backtest("2025-08-01", days=15)