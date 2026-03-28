import json
import datetime
from model import MLBPredictor

DATASET_PATH = 'data_odds/mlb_odds_dataset.json'
CONFIDENCE_THRESHOLD = 0.55 

def load_odds_data():
    print("📂 Cargando dataset de cuotas reales...")
    with open(DATASET_PATH, 'r') as f:
        return json.load(f)

def get_real_odds(odds_data, date_str, home_team, away_team):
    """Busca momios en la estructura anidada de gameView."""
    day_games = odds_data.get(date_str, [])
    if not day_games:
        return None, None

    # Slug para machear (ej: "Guardians")
    h_slug = home_team.split()[-1].lower()
    
    for game in day_games:
        # Extraemos nombres de la estructura 'gameView'
        gv = game.get('gameView', {})
        h_name_json = gv.get('homeTeam', {}).get('fullName', '').lower()
        
        if h_slug in h_name_json:
            # Buscamos en la lista de 'moneyline'
            ml_list = game.get('odds', {}).get('moneyline', [])
            
            # Buscamos DraftKings, si no, Bet365, si no, el primero que aparezca
            line_data = None
            for book in ml_list:
                if book.get('sportsbook') == 'draftkings':
                    line_data = book.get('currentLine')
                    break
            
            if not line_data and ml_list:
                line_data = ml_list[0].get('currentLine')

            if line_data:
                return line_data.get('homeOdds'), line_data.get('awayOdds')
    
    return None, None

def calculate_payout(odds, stake=1.0):
    if odds > 0: return stake * (odds / 100)
    return stake * (100 / abs(odds))

def run_real_roi_backtest(start_date_str, days=45):
    predictor = MLBPredictor(use_calibrator=True)
    odds_data = load_odds_data()
    start_dt = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
    
    stats = {'total': 0, 'bets': 0, 'won': 0, 'profit': 0.0}

    print(f"\n🚀 AUDITORÍA ROI REAL (Muestra: {days} días)")
    
    for i in range(days):
        date_str = (start_dt + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        print(f"🔍 Procesando {date_str}...", end='\r')
        
        games = predictor.loader.get_schedule(date_str)
        for g in games:
            if g['status'] != 'Final': continue
            
            h_odds, a_odds = get_real_odds(odds_data, date_str, g['home_name'], g['away_name'])
            if h_odds is None: continue
            
            res = predictor.predict_game(g)
            if 'error' in res: continue
            
            stats['total'] += 1
            if res['confidence'] >= CONFIDENCE_THRESHOLD:
                stats['bets'] += 1
                pick, winner = res['winner'], g['real_winner']
                curr_odds = h_odds if pick == g['home_name'] else a_odds
                
                if pick == winner:
                    stats['won'] += 1
                    p = calculate_payout(curr_odds)
                    stats['profit'] += p
                    print(f"✅ {date_str} | {pick} ({curr_odds}) | +{p:.2f}u")
                else:
                    stats['profit'] -= 1.0
                    print(f"❌ {date_str} | {pick} ({curr_odds}) | -1.00u")

    print("\n" + "="*40)
    print(f"🏁 RESULTADO FINAL - {days} DÍAS")
    if stats['bets'] > 0:
        roi = (stats['profit']/stats['bets'])*100
        print(f"Apuestas: {stats['bets']} | Ganancia: {stats['profit']:.2f}u")
        print(f"ROI REAL: {roi:.2f}%")
        print(f"Precisión: {(stats['won']/stats['bets'])*100:.1f}%")
    else:
        print("No se realizaron apuestas con los criterios establecidos.")
    print("="*40)

if __name__ == "__main__":
    # Ahora sí, los 45 días de puro fuego real
    run_real_roi_backtest("2024-08-01", days=45)