import json
import datetime
from model import MLBPredictor

DATASET_PATH = 'data_odds/mlb_odds_dataset.json'
CONFIDENCE_THRESHOLD = 0.58 # Subimos un poco la vara para Kelly
MAX_ODDS_LIMIT = -250       # NO apostamos a nada más caro que -250 (ej. -300, -400 fuera)
KELLY_FRACTION = 0.25       # Usamos 1/4 de Kelly para seguridad

def load_odds_data():
    with open(DATASET_PATH, 'r') as f:
        return json.load(f)

def american_to_decimal(american):
    if american > 0: return (american / 100) + 1
    return (100 / abs(american)) + 1

def calculate_kelly(prob_win, american_odds):
    """Calcula el porcentaje del bankroll a apostar."""
    b = american_to_decimal(american_odds) - 1
    q = 1 - prob_win
    f_star = (b * prob_win - q) / b
    return max(0, f_star * KELLY_FRACTION)

def get_real_odds(odds_data, date_str, home_team):
    day_games = odds_data.get(date_str, [])
    h_slug = home_team.split()[-1].lower()
    for game in day_games:
        gv = game.get('gameView', {})
        if h_slug in gv.get('homeTeam', {}).get('fullName', '').lower():
            ml_list = game.get('odds', {}).get('moneyline', [])
            for book in ml_list:
                if book.get('sportsbook') == 'draftkings':
                    line = book.get('currentLine')
                    return line.get('homeOdds'), line.get('awayOdds')
    return None, None

def run_kelly_backtest(start_date_str, days=45):
    predictor = MLBPredictor(use_calibrator=True)
    odds_data = load_odds_data()
    start_dt = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
    
    bankroll = 100.0 # Empezamos con 100 unidades "teóricas"
    stats = {'bets': 0, 'won': 0, 'profit': 0.0}

    print(f"\n📈 AUDITORÍA KELLY CRITERION (Limit: {MAX_ODDS_LIMIT})")
    print("-" * 50)

    for i in range(days):
        date_str = (start_dt + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        games = predictor.loader.get_schedule(date_str)
        
        for g in games:
            if g['status'] != 'Final': continue
            h_odds, a_odds = get_real_odds(odds_data, date_str, g['home_name'])
            if h_odds is None: continue

            res = predictor.predict_game(g)
            if 'error' in res: continue
            
            # --- FILTRO 1: Confianza ---
            prob = res['confidence']
            if prob < CONFIDENCE_THRESHOLD: continue
            
            # --- FILTRO 2: Límite de Momio ---
            pick = res['winner']
            curr_odds = h_odds if pick == g['home_name'] else a_odds
            
            # Si el momio es muy caro (ej: -300 < -250), saltamos
            if curr_odds < 0 and curr_odds < MAX_ODDS_LIMIT:
                continue

            # --- CÁLCULO DE STAKE (KELLY) ---
            stake_pct = calculate_kelly(prob, curr_odds)
            if stake_pct <= 0: continue # No hay ventaja real
            
            stake_units = bankroll * stake_pct
            stats['bets'] += 1
            
            if pick == g['real_winner']:
                stats['won'] += 1
                # Ganancia neta = stake * (decimal_odds - 1)
                p = stake_units * (american_to_decimal(curr_odds) - 1)
                bankroll += p
                print(f"✅ {date_str} | {pick} ({curr_odds}) | Stake: {stake_units:.2f}u | +{p:.2f}u")
            else:
                bankroll -= stake_units
                print(f"❌ {date_str} | {pick} ({curr_odds}) | Stake: {stake_units:.2f}u | -{stake_units:.2f}u")

    print("\n" + "="*40)
    print(f"🏁 RESULTADO ESTRATEGIA KELLY")
    print(f"Bankroll Final: {bankroll:.2f} unidades")
    print(f"Crecimiento Total: {((bankroll - 100)/100)*100:.2f}%")
    print(f"Precisión: {(stats['won']/stats['bets'])*100 if stats['bets']>0 else 0:.1f}%")
    print("="*40)

if __name__ == "__main__":
    run_kelly_backtest("2024-08-01", days=45)