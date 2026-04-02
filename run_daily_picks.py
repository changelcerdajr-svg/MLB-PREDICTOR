# run_daily_picks.py
import json
import datetime
from model import MLBPredictor
from financial import american_to_prob, get_fair_prob, calculate_edge, calculate_kelly
import tracker # Importamos tu base de datos local
from hot_hand_updater import update_hot_hand_database # <-- Integración V19.0

LIVE_ODDS_PATH = 'data_odds/live_odds.json'
CONFIDENCE_THRESHOLD = 0.55001 # Ajustado al estándar de la V19.0
MAX_ODDS_LIMIT = -250       
KELLY_FRACTION = 0.25       
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
    print("Iniciando Terminal de Operaciones V19.0 (Scraping + Hot Hand)...")
    
    # 1. ACTUALIZACIÓN AUTOMÁTICA CAPA 2 (CRÍTICO PARA V19.0)
    print("\n[1] Actualizando Sincronización Biomecánica (Últimos 10 días)...")
    success = update_hot_hand_database()
    if not success:
        print("Advertencia: No se pudo actualizar el Hot Hand. Usando talento base (Capa 1).")
        
    print("\n[2] Inicializando Motor de Monte Carlo...")
    predictor = MLBPredictor(use_calibrator=True, use_hot_hand=True)
    odds_data = load_live_odds()
    
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    print(f"Buscando juegos programados para hoy: {today_str}")
    games = predictor.loader.get_schedule(today_str)
    
    if not games:
        print("No hay juegos programados en la MLB para hoy.")
        return

    print("-" * 50)
    print(f"BANKROLL ACTUAL: ${CURRENT_BANKROLL:.2f}")
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

        stake_pct = calculate_kelly(prob, curr_odds, fraction=KELLY_FRACTION)
        if stake_pct <= 0: continue 
        
        stake_amount = CURRENT_BANKROLL * stake_pct
        bets_found += 1
        
        # Cálculos para el Tracker
        game_title = f"{g['away_name']} @ {g['home_name']}"
        # Eliminación del Vig: Obtenemos el Fair Value real
        fair_h, fair_a = get_fair_prob(h_odds, a_odds)
        
        # Seleccionamos la probabilidad justa que corresponde a nuestro pick
        market_prob = fair_h if pick == g['home_name'] else fair_a
        
        # Cálculo de Edge Real (Alpha) sobre Fair Value usando el motor financiero
        edge_report = calculate_edge(prob, market_prob)
        edge = edge_report['edge']

        # Si después de quitar el Vig el Edge es negativo o cero, abortamos la operación
        if edge <= 0:
            continue
        
        print(f"\nAPUESTA APROBADA: {game_title}")
        print(f"PICK: {pick} | Prob Modelo: {prob*100:.1f}% | Momio: {curr_odds}")
        print(f"INVERSIÓN: ${stake_amount:.2f} ({stake_pct*100:.2f}% del Bankroll)")
        
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
            print("[Registrado con éxito en history_log.csv]")
        else:
            print("[Esta apuesta ya estaba registrada previamente]")

    if bets_found == 0:
        print("\nEl modelo no encontró valor matemático en los momios actuales. Capital protegido.")

if __name__ == "__main__":
    generate_daily_picks()