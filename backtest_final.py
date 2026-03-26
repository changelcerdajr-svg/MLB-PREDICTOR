# backtest_final.py
# Auditoría Institucional Out-of-Sample - V13.2 (Filtro de Confianza)
import sys
from datetime import datetime, timedelta
from model import MLBPredictor

# --- CONFIGURACIÓN DEL BACKTEST ---
START_DATE = "2024-07-01"  
DAYS_TO_TEST = 60          
MIN_CONFIDENCE = 0.55      # NUEVO: El modelo solo opera si la confianza es >= 55%

def run_backtest():
    print("="*50)
    print(" 🔬 AUDITORÍA INSTITUCIONAL V13.2 (Out-of-Sample)")
    print(f" 📅 Desde: {START_DATE} | Periodo: {DAYS_TO_TEST} días")
    print(f" 🎯 Filtro de Confianza (Threshold): {MIN_CONFIDENCE*100}%")
    print("="*50)

    try:
        predictor = MLBPredictor()
        # FIX ESTRUCTURAL: El modo histórico se activa UNA SOLA VEZ para todo el backtest
        predictor.loader._force_historical_mode = True
    except Exception as e:
        print(f"Error inicializando el motor: {e}")
        return

    current_date = datetime.strptime(START_DATE, "%Y-%m-%d")
    
    # Contadores Maestros
    total_valid_games = 0
    rejected_games = 0
    
    # Contadores de Apuestas (Actionable Games)
    games_bet = 0
    correct_bets = 0
    home_wins_in_bets = 0 

    for i in range(DAYS_TO_TEST):
        test_date = current_date.strftime("%Y-%m-%d")
        # Imprimimos en la misma línea para no saturar la terminal
        sys.stdout.write(f"\rProcesando: {test_date}...")
        sys.stdout.flush()
        
        try:
            games = predictor.loader.get_schedule(test_date)
        except Exception as e:
            current_date += timedelta(days=1)
            continue
            
        if not games:
            current_date += timedelta(days=1)
            continue

        for game in games:
            home_score = game['real_score']['home']
            away_score = game['real_score']['away']
            
            if home_score == away_score:
                continue
                
            real_winner = game['real_winner']
            
            # Ejecutamos la predicción
            res = predictor.predict_game(game)
            
            # Compuerta 1: Riesgo (Datos Incompletos)
            if 'error' in res:
                rejected_games += 1
                continue
                
            total_valid_games += 1
            predicted_winner = res['winner']
            confidence = res['confidence']
            
            # Compuerta 2: Filtro de Confianza (El Sniper)
            if confidence >= MIN_CONFIDENCE:
                games_bet += 1
                
                if predicted_winner == real_winner:
                    correct_bets += 1
                    
                if real_winner == game['home_name']:
                    home_wins_in_bets += 1
                
        # Avanzamos al siguiente día
        current_date += timedelta(days=1)
        
    # --- REPORTE FINAL ---
    print("\n\n" + "="*50)
    print(" 📊 RESULTADOS OUT-OF-SAMPLE (V13.2)")
    print("="*50)
    
    total_games_seen = total_valid_games + rejected_games
    if total_games_seen > 0:
        print(f" 🛑 Rechazos por falta de datos: {(rejected_games/total_games_seen)*100:.1f}% ({rejected_games}/{total_games_seen})")
        
        ignored_games = total_valid_games - games_bet
        print(f" 🙈 Juegos ignorados (Baja Confianza < {MIN_CONFIDENCE*100}%): {ignored_games}")
        print("-" * 50)
        
        if games_bet > 0:
            accuracy = (correct_bets / games_bet) * 100
            real_baseline = (home_wins_in_bets / games_bet) * 100
            real_lift = accuracy - real_baseline
            
            print(f" 💰 JUEGOS OPERADOS (Actionable): {games_bet}")
            print(f" 🎯 ACCURACY EN APUESTAS: {accuracy:.2f}% ({correct_bets}/{games_bet})")
            print(f" 🏠 BASELINE EN APUESTAS: {real_baseline:.2f}%")
            print(f" 🚀 LIFT REAL DEL MODELO: {real_lift:+.2f}%")
            
            print("-" * 50)
            if real_lift > 0:
                print(" ✅ SEÑAL ALPHA CONFIRMADA: El modelo extrae valor real en su zona de confianza.")
            else:
                print(" ⚠️ ALERTA: Aún filtrando, el modelo no supera la varianza del mercado.")
        else:
            print(" 📉 El filtro es muy estricto. El modelo no encontró ninguna oportunidad operable.")
    else:
        print(" No se procesó ningún juego.")

if __name__ == "__main__":
    run_backtest()