import json
import datetime
from model import MLBPredictor

LIVE_ODDS_PATH = 'data_odds/live_odds.json'
CONFIDENCE_THRESHOLD = 0.58 
MAX_ODDS_LIMIT = -250       
KELLY_FRACTION = 0.25       
CURRENT_BANKROLL = 1000.0   # Ajusta esto a tu capital real disponible

def load_live_odds():
    try:
        with open(LIVE_ODDS_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: No se encontró live_odds.json. Corre el scraper primero.")
        return {}

def american_to_decimal(american):
    if american > 0: return (american / 100) + 1
    return (100 / abs(american)) + 1

def calculate_kelly(prob_win, american_odds):
    b = american_to_decimal(american_odds) - 1
    q = 1 - prob_win
    f_star = (b * prob_win - q) / b
    return max(0, f_star * KELLY_FRACTION)

def get_today_odds(odds_data, date_str, home_team):
    day_games = odds_data.get(date_str, [])
    if not day_games: return None, None
    
    h_slug = home_team.split()[-1].lower()
    for game in day_games:
        gv = game.get('gameView', {})
        if h_slug in gv.get('homeTeam', {}).get('fullName', '').lower():
            ml_list = game.get('odds', {}).get('moneyline', [])
            for book in ml_list:
                # Buscamos DraftKings o la casa que haya extraído tu scraper
                if book.get('sportsbook') == 'draftkings':
                    line = book.get('currentLine')
                    return line.get('homeOdds'), line.get('awayOdds')
    return None, None

def generate_daily_picks():
    print("Iniciando Terminal de Operaciones V17.2 (Modo Rayos X)...")
    predictor = MLBPredictor(use_calibrator=True)
    odds_data = load_live_odds()
    
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    print(f"Buscando juegos programados para hoy: {today_str}")
    games = predictor.loader.get_schedule(today_str)
    
    if not games:
        print("No hay juegos programados para hoy en la API de MLB.")
        return

    print("-" * 50)
    print(f"BANKROLL ACTUAL: ${CURRENT_BANKROLL:.2f}")
    print("-" * 50)
    
    bets_found = 0

    for g in games:
        if g['status'] in ['Final', 'In Progress']: continue
            
        print(f"\nAnalizando: {g['away_name']} @ {g['home_name']}")
        
        h_odds, a_odds = get_today_odds(odds_data, today_str, g['home_name'])
        if h_odds is None:
            print(" -> Descartado: No se encontraron momios de DraftKings en el scraper para este juego.")
            continue

        res = predictor.predict_game(g)
        if 'error' in res:
            print(f" -> Descartado: Faltan datos estadísticos de los pitchers ({res.get('error')}).")
            continue
        
        prob = res['confidence']
        pick = res['winner']
        curr_odds = h_odds if pick == g['home_name'] else a_odds
        
        print(f" -> Predicción: {pick} ({prob*100:.1f}%) | Momio: {curr_odds}")
        
        if prob < CONFIDENCE_THRESHOLD:
            print(f" -> Descartado: Confianza insuficiente (Requiere {CONFIDENCE_THRESHOLD*100}%, tiene {prob*100:.1f}%).")
            continue
        
        if curr_odds < 0 and curr_odds < MAX_ODDS_LIMIT:
            print(f" -> Descartado: El momio es demasiado caro para el riesgo (Límite {MAX_ODDS_LIMIT}).")
            continue

        stake_pct = calculate_kelly(prob, curr_odds)
        if stake_pct <= 0:
            print(" -> Descartado: La fórmula de Kelly indica Edge negativo (La casa tiene la ventaja).")
            continue 
        
        stake_amount = CURRENT_BANKROLL * stake_pct
        bets_found += 1
        
        print(f"\n*** APUESTA APROBADA ***")
        print(f"PICK: {pick} | Ventaja Matemática Detectada")
        print(f"INVERSIÓN RECOMENDADA: ${stake_amount:.2f} ({stake_pct*100:.2f}% del Bankroll)")

    if bets_found == 0:
        print("\n" + "-" * 50)
        print("El modelo no encontró valor en los momios actuales. Capital protegido.")

if __name__ == "__main__":
    generate_daily_picks()
