# backtest_final.py
# Laboratorio de Auditoría V12.0 (Cero Fuga de Datos)

from model import MLBPredictor
from datetime import datetime, timedelta
import sys

# CONFIGURACIÓN: ESTRICTAMENTE DESPUÉS DE LA CALIBRACIÓN
START_DATE = "2024-07-01" 
GAMES_TO_TEST = 1000       

def run_backtest():
    print("\n==================================================")
    print("  AUDITORÍA INSTITUCIONAL V12.0 (Out-of-Sample)")
    print(f"  Desde: {START_DATE}")
    print("==================================================\n")

    predictor = MLBPredictor(use_calibrator=True)
    loader = predictor.loader
    
    current_date = datetime.strptime(START_DATE, "%Y-%m-%d")
    
    total_processed = 0
    correct_predictions = 0
    rejected_games = 0
    
    while (total_processed + rejected_games) < GAMES_TO_TEST:
        date_str = current_date.strftime("%Y-%m-%d")
        games = loader.get_schedule(date_str)
        
        if not games:
            current_date += timedelta(days=1)
            continue

        for game in games:
            if game['status'] not in ['Final', 'Game Over', 'Completed']: continue
            if (total_processed + rejected_games) >= GAMES_TO_TEST: break

            try:
                prediction = predictor.predict_game(game)
                
                if 'error' in prediction:
                    rejected_games += 1
                    continue
                
                predicted_winner = prediction['winner']
                real_winner = game['real_winner']
                
                if predicted_winner == real_winner:
                    correct_predictions += 1
                
                total_processed += 1
                
                sys.stdout.write(f"\rAceptados: {total_processed} | Rechazados: {rejected_games}")
                sys.stdout.flush()
                
            except Exception as e:
                pass

        current_date += timedelta(days=1)

    total_games = total_processed + rejected_games
    print("\n\n" + "="*50)
    print(" RESULTADOS OUT-OF-SAMPLE (SIN DATA LEAKAGE)")
    print("="*50)
    
    if total_games > 0:
        rejection_rate = (rejected_games / total_games) * 100
        print(f" Tasa de Rechazo (Falta Info): {rejection_rate:.1f}%")
        print("-" * 50)
        
        if total_processed > 0:
            accuracy = (correct_predictions / total_processed) * 100
            print(f" ACCURACY REAL: {accuracy:.2f}% ({correct_predictions}/{total_processed})")
    else:
        print("No se procesaron juegos.")

if __name__ == "__main__":
    run_backtest()