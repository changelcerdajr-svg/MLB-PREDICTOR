# backtest.py
# Auditoría Histórica V16.0 (Motor Statcast)

from model import MLBPredictor
from datetime import datetime, timedelta

def run_historical_backtest():
    print("="*60)
    print(" 🔬 INICIANDO BACKTEST HISTÓRICO V16.0 (STATCAST)")
    print("="*60)
    
    # Definir la ventana del pasado (Primavera 2024)
    START_DATE = "2024-04-01"
    END_DATE = "2024-05-31" 
    
    # Apagamos el calibrador para evaluar el poder crudo del nuevo motor
    predictor = MLBPredictor(use_calibrator=False) 
    predictor.loader._force_historical_mode = True 
    
    current_date = datetime.strptime(START_DATE, "%Y-%m-%d")
    end_date = datetime.strptime(END_DATE, "%Y-%m-%d")
    
    total_games = 0
    actionable_games = 0
    wins = 0
    home_wins = 0
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        print(f"\n📅 Analizando {date_str}...", end=" ")
        
        games = predictor.loader.get_schedule(date_str)
        
        if not games:
            print("Sin juegos.")
            current_date += timedelta(days=1)
            continue
            
        print(f"[{len(games)} juegos]")
        
        for game in games:
            if game['status'] not in ['Final', 'Game Over', 'Completed', 'F']:
                continue
                
            try:
                h_score = game['real_score']['home']
                a_score = game['real_score']['away']
                if h_score == a_score: continue
                
                real_winner = game['home_name'] if h_score > a_score else game['away_name']
                
                # Predecir el juego usando el motor Statcast V16.0
                res = predictor.predict_game(game)
                if 'error' in res: continue
                
                total_games += 1
                if real_winner == game['home_name']:
                    home_wins += 1
                    
                # Compuerta de confianza estricta (> 55%)
                if res['confidence'] >= 0.55:
                    actionable_games += 1
                    if res['winner'] == real_winner:
                        wins += 1
            except Exception as e:
                pass
                    
        current_date += timedelta(days=1)
        
    print("\n" + "="*60)
    print(" 📊 RESULTADOS DEL BACKTEST (STATCAST V16.0)")
    print("="*60)
    print(f"Juegos Totales Evaluados: {total_games}")
    
    if actionable_games > 0:
        accuracy = wins / actionable_games
        baseline = home_wins / total_games
        lift = accuracy - baseline
        
        print(f"💰 JUEGOS OPERADOS (Confianza > 55%): {actionable_games}")
        print(f"🎯 ACCURACY EN APUESTAS: {accuracy*100:.2f}% ({wins}/{actionable_games})")
        print(f"🏠 BASELINE DEL MERCADO: {baseline*100:.2f}%")
        
        if lift > 0:
            print(f"🚀 LIFT REAL DEL MODELO: +{lift*100:.2f}% (Señal Alpha Detectada)")
        else:
            print(f"⚠️ LIFT NEGATIVO: {lift*100:.2f}% (Ruido en el modelo)")
    else:
        print("No hubo juegos que superaran el umbral de confianza del 55%.")
    print("="*60)

if __name__ == "__main__":
    run_historical_backtest()