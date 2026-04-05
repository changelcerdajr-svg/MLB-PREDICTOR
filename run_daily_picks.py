# run_daily_picks.py
import json
import datetime
from model import MLBPredictor
from financial import american_to_prob, get_fair_prob, calculate_edge, calculate_kelly
import tracker 
from hot_hand_updater import update_hot_hand_database 
from config import CONFIDENCE_THRESHOLD, MAX_ODDS_LIMIT, KELLY_FRACTION, MAX_SENSITIVITY

LIVE_ODDS_PATH = 'data_odds/live_odds.json'    
CURRENT_BANKROLL = 1000.0   

def load_live_odds():
    try:
        with open(LIVE_ODDS_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: No se encontró live_odds.json. Corre 'python live_odds_scraper.py' primero.")
        return {}

def get_today_odds(odds_data, date_str, mlb_home_name):
    day_games = odds_data.get(date_str, [])
    if not day_games: return None, None
    mlb_clean = mlb_home_name.lower().strip()
    
    for game in day_games:
        dk_name = game.get('gameView', {}).get('homeTeam', {}).get('fullName', '').lower().strip()
        if mlb_clean in dk_name or dk_name in mlb_clean:
            ml_list = game.get('odds', {}).get('moneyline', [])
            for book in ml_list:
                if book['sportsbook'] in ['draftkings', 'vegas_consensus']:
                    line = book.get('currentLine')
                    if line: return line.get('homeOdds'), line.get('awayOdds')
    return None, None

def generate_daily_picks():
    print("Iniciando MLB Predictor - Buscando Picks de Valor...")
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    odds_data = load_live_odds()
    if not odds_data:
        return
        
    predictor = MLBPredictor()
    games = predictor.loader.get_schedule(today_str)
    
    if not games:
        print("No hay juegos programados para hoy o hubo un error al obtenerlos.")
        return
        
    bets_found = 0
    
    for game in games:
        if game['status'] in ['Final', 'In Progress']: 
            continue
            
        h_odds, a_odds = get_today_odds(odds_data, today_str, game['home_name'])
        if h_odds is None or a_odds is None: 
            continue

        # 1. Predicción cruda
        res = predictor.predict_game(game)
        if 'error' in res: 
            continue
            
        home_prob = res['home_prob']
        away_prob = res['away_prob']
        max_prob = max(home_prob, away_prob)
        
        # =========================================================
        # CANDADO 1: FILTRO DE CONFIANZA CENTRALIZADO
        # =========================================================
        if max_prob < CONFIDENCE_THRESHOLD:
            continue
            
        # =========================================================
        # CANDADO 2: FILTRO DE SENSIBILIDAD E INCERTIDUMBRE (FIX #4)
        # =========================================================
        sensitivity = res.get('raw_sensitivity', 1.0)
        if sensitivity > MAX_SENSITIVITY:
            print(f"  [NOISE] {game['home_name']} vs {game['away_name']}: ±{sensitivity*100:.1f}% incertidumbre. Saltando.")
            continue
            
        # 3. Datos de la apuesta
        pick = game['home_name'] if max_prob == home_prob else game['away_name']
        prob = max_prob
        curr_odds = h_odds if pick == game['home_name'] else a_odds
        game_title = f"{game['away_name']} @ {game['home_name']}"
        
        # Límite de Momios Fuertes (ej. no apostar a un -300)
        if curr_odds < MAX_ODDS_LIMIT:
            continue

        # 4. Finanzas e Inversión
        fair_h, fair_a = get_fair_prob(h_odds, a_odds)
        market_prob = fair_h if pick == game['home_name'] else fair_a
        
        edge_report = calculate_edge(prob, market_prob)
        edge = edge_report['edge']

        # Si el Edge es negativo, abortamos
        if edge <= 0:
            continue
            
        bets_found += 1
        
        # Cálculo de Criterio de Kelly (Tamaño de Inversión)
        stake_pct = calculate_kelly(prob, curr_odds, fraction=KELLY_FRACTION)
        stake_amount = CURRENT_BANKROLL * stake_pct
        
        print(f"\n✅ APUESTA APROBADA: {game_title}")
        print(f"PICK: {pick} | Prob Modelo: {prob*100:.1f}% | Momio: {curr_odds}")
        print(f"INVERSIÓN: ${stake_amount:.2f} ({stake_pct*100:.2f}% del Bankroll)")
        
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
            print("[Registrado con éxito en history_log.csv]")
        else:
            print("[Esta apuesta ya estaba registrada previamente]")

    if bets_found == 0:
        print("\nEl modelo no encontró valor matemático en los momios actuales. Capital protegido.")

if __name__ == "__main__":
    generate_daily_picks()