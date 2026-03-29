# backtest_master.py
# Motor de Validación Institucional V17.3 (Kelly + Flat ROI + Alpha True)

import json
import datetime
from model import MLBPredictor

# --- CONFIGURACIÓN ESTRATÉGICA ---
DATASET_PATH = 'data_odds/mlb_odds_dataset.json'
CONFIDENCE_THRESHOLD = 0.55  # Umbral mínimo de confianza para operar
MAX_ODDS_LIMIT = -250        # Bloqueo de favoritos extremos
KELLY_FRACTION = 0.25        # 1/4 Kelly para protección de capital
STARTING_BANKROLL = 1000.0   # Capital inicial ficticio para simulación Kelly

def load_odds_data():
    try:
        with open(DATASET_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error cargando momios: {e}")
        return {}

def american_to_decimal(american):
    if american > 0: return (american / 100) + 1
    return (100 / abs(american)) + 1

def calculate_payout_flat(odds, stake=1.0):
    """Calcula ganancia neta para apuestas planas de 1 unidad."""
    if odds > 0: return stake * (odds / 100)
    return stake * (100 / abs(odds))

def calculate_kelly_stake(prob_win, american_odds):
    """Calcula el % de bankroll según Criterio de Kelly."""
    b = american_to_decimal(american_odds) - 1
    q = 1 - prob_win
    f_star = (b * prob_win - q) / b
    return max(0, f_star * KELLY_FRACTION)

def get_real_odds(odds_data, date_str, mlb_home_name):
    """Busca momios con matching robusto para evitar sesgo de selección."""
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
            
            # Fallback si no hay DK
            if ml_list:
                line = ml_list[0].get('currentLine')
                if line: return line.get('homeOdds'), line.get('awayOdds')
    return None, None

def run_master_backtest(start_date_str, days=45):
    # ATENCIÓN: use_calibrator=False para el Test de la Verdad (Alpha puro)
    predictor = MLBPredictor(use_calibrator=False) 
    odds_data = load_odds_data()
    start_dt = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
    
    bankroll = STARTING_BANKROLL
    stats = {
        'total_games': 0, 'bets': 0, 'won': 0, 
        'flat_profit': 0.0, 'baseline_home_wins': 0
    }

    print("=" * 60)
    print(f"🚀 INICIANDO BACKTEST MASTER V17.3: {start_date_str} (+{days} días)")
    print(f"Filtros: Confianza > {CONFIDENCE_THRESHOLD*100}% | Límite Momio: {MAX_ODDS_LIMIT}")
    print("=" * 60)
    
    for i in range(days):
        date_str = (start_dt + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        games = predictor.loader.get_schedule(date_str)
        
        for g in games:
            if g['status'] != 'Final': continue
            stats['total_games'] += 1
            
            if g['real_winner'] == g['home_name']:
                stats['baseline_home_wins'] += 1
                
            h_odds, a_odds = get_real_odds(odds_data, date_str, g['home_name'])
            if h_odds is None: continue
            
            res = predictor.predict_game(g)
            if 'error' in res: continue
            
            prob = res['confidence']
            if prob < CONFIDENCE_THRESHOLD: continue
            
            pick, winner = res['winner'], g['real_winner']
            curr_odds = h_odds if pick == g['home_name'] else a_odds
            
            # Filtro de Riesgo: No apostar a favoritos extremos
            if curr_odds < 0 and curr_odds < MAX_ODDS_LIMIT: continue
            
            # Cálculo Kelly
            stake_pct = calculate_kelly_stake(prob, curr_odds)
            if stake_pct <= 0: continue
            
            stake_units = bankroll * stake_pct
            stats['bets'] += 1
            
            # Resolución de la apuesta
            if pick == winner:
                stats['won'] += 1
                # Gestión Flat (1 unidad)
                flat_payout = calculate_payout_flat(curr_odds)
                stats['flat_profit'] += flat_payout
                # Gestión Kelly
                kelly_payout = stake_units * (american_to_decimal(curr_odds) - 1)
                bankroll += kelly_payout
                print(f"✅ {date_str} | {pick} ({curr_odds}) | Prob: {prob*100:.1f}% | Stake: ${stake_units:.2f} | +${kelly_payout:.2f}")
            else:
                stats['flat_profit'] -= 1.0
                bankroll -= stake_units
                print(f"❌ {date_str} | {pick} ({curr_odds}) | Prob: {prob*100:.1f}% | Stake: ${stake_units:.2f} | -${stake_units:.2f}")

    # --- REPORTE INSTITUCIONAL ---
    print("\n" + "=" * 60)
    print("📊 REPORTE DE RENDIMIENTO - MASTER BACKTEST")
    print("=" * 60)
    
    if stats['bets'] > 0:
        win_rate = (stats['won'] / stats['bets']) * 100
        flat_roi = (stats['flat_profit'] / stats['bets']) * 100
        kelly_growth = ((bankroll - STARTING_BANKROLL) / STARTING_BANKROLL) * 100
        baseline = (stats['baseline_home_wins'] / stats['total_games']) * 100 if stats['total_games'] > 0 else 0
        lift = win_rate - baseline
        
        print(f"Juegos Evaluados:     {stats['total_games']}")
        print(f"Apuestas Realizadas:  {stats['bets']} (Filtro superado)")
        print(f"Precisión (Win Rate): {win_rate:.2f}%")
        print(f"Baseline (Locales):   {baseline:.2f}%")
        print(f"Edge sobre Mercado:   +{lift:.2f}% {'🚀 (Alpha)' if lift > 2.0 else '⚠️ (Marginal)'}")
        print("-" * 60)
        print(f"Estrategia FLAT (1u): {stats['flat_profit']:+.2f} unidades (ROI: {flat_roi:+.2f}%)")
        print(f"Estrategia KELLY:     Capital final ${bankroll:.2f} (Crecimiento: {kelly_growth:+.2f}%)")
    else:
        print("El modelo no encontró apuestas que cumplieran los criterios de riesgo.")
    print("=" * 60)

if __name__ == "__main__":
    # Corremos los mismos 45 días del dataset histórico
    run_master_backtest("2024-08-01", days=45)