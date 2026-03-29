import json
import datetime
from model import MLBPredictor
from financial import american_to_prob # Importamos de tu módulo financiero
import tracker # Importamos tu base de datos local

LIVE_ODDS_PATH = 'data_odds/live_odds.json'
CONFIDENCE_THRESHOLD = 0.55 
MAX_ODDS_LIMIT = -250       
KELLY_FRACTION = 0.25       
CURRENT_BANKROLL = 1000.0   

def load_live_odds():
    try:
        with open(LIVE_ODDS_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ Error: No se encontró live_odds.json. Corre 'python live_odds_scraper.py' primero.")
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

def generate_daily_picks():
    print("🤖 Iniciando Terminal de Operaciones V17.3 (Scraping Independiente)...")
    predictor = MLBPredictor(use_calibrator=False) # Usamos Alpha puro
    odds_data = load_live_odds()
    
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    print(f"📅 Buscando juegos programados para hoy: {today_str}")
    games = predictor.loader.get_schedule(today_str)
    
    if not games:
        print("No hay juegos programados en la MLB para hoy.")
        return

    print("-" * 50)
    print(f"💵 BANKROLL ACTUAL: ${CURRENT_BANKROLL:.2f}")
    print("-" * 50)
    
    bets_found = 0

    for g in games:
        if g['status'] in ['Final', 'In Progress']: continue
            
        h_odds, a_odds = get_today_odds(odds_data, today_str, g['home_name'])
        if h_odds is None: continue

        res = predictor.predict_game(g)
        if 'error' in res: continue
        
        prob = res['confidence']
        pick = res['winner']
        curr_odds = h_odds if pick == g['home_name'] else a_odds
        
        # Filtros de Riesgo
        if prob < CONFIDENCE_THRESHOLD: continue
        if curr_odds < 0 and curr_odds < MAX_ODDS_LIMIT: continue

        stake_pct = calculate_kelly(prob, curr_odds)
        if stake_pct <= 0: continue 
        
        stake_amount = CURRENT_BANKROLL * stake_pct
        bets_found += 1
        
        # Cálculos para el Tracker
        game_title = f"{g['away_name']} @ {g['home_name']}"
        market_prob = american_to_prob(curr_odds)
        edge = prob - market_prob
        
        print(f"\n✅ APUESTA APROBADA: {game_title}")
        print(f"👉 PICK: {pick} | Prob Modelo: {prob*100:.1f}% | Momio: {curr_odds}")
        print(f"💰 INVERSIÓN: ${stake_amount:.2f} ({stake_pct*100:.2f}% del Bankroll)")
        
        # Guardar automáticamente en el historial (CSV)
        saved = tracker.log_bet(
            fecha=today_str,
            juego=game_title,
            pick=pick,
            confianza=prob * 100,
            prob_mercado=market_prob,
            cuota=curr_odds,
            edge=round(edge * 100, 2)
        )
        
        if saved:
            print("💾 [Registrado con éxito en history_log.csv]")
        else:
            print("⚠️ [Esta apuesta ya estaba registrada previamente]")

    if bets_found == 0:
        print("\nEl modelo no encontró valor matemático en los momios actuales. Capital protegido.")

if __name__ == "__main__":
    generate_daily_picks()