# backtest_final.py
# Laboratorio de Auditoría: Medición de Accuracy y Sesgo de Selección (Gate Rejections)

from model import MLBPredictor
from datetime import datetime, timedelta
import sys

# CONFIGURACIÓN
START_DATE = "2024-06-01" 
GAMES_TO_TEST = 1000       

def run_backtest():
    print("\n" + "🧪 "*15)
    print(f"  INICIANDO AUDITORÍA (Control de Sesgo de Selección)")
    print(f"  Desde: {START_DATE}")
    print("🧪 "*15 + "\n")

    predictor = MLBPredictor()
    loader = predictor.loader
    
    current_date = datetime.strptime(START_DATE, "%Y-%m-%d")
    
    total_processed = 0
    correct_predictions = 0
    
    # Tracking de Sesgo de Selección
    rejected_games = 0
    rejected_home_wins = 0
    
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
                
                # --- AUDITORÍA DE COMPUERTAS (GATE REJECTIONS) ---
                if 'error' in prediction:
                    rejected_games += 1
                    if game['real_winner'] == game['home_name']:
                        rejected_home_wins += 1
                    continue
                
                # --- JUEGOS ACEPTADOS ---
                predicted_winner = prediction['winner']
                real_winner = game['real_winner']
                
                if predicted_winner == real_winner:
                    correct_predictions += 1
                
                total_processed += 1
                
                sys.stdout.write(f"\r✅ Aceptados: {total_processed} | 🛑 Rechazados: {rejected_games}")
                sys.stdout.flush()
                
            except Exception as e:
                pass

        current_date += timedelta(days=1)

    # REPORTE DE SESGO Y RESULTADOS
    total_games = total_processed + rejected_games
    print("\n\n" + "="*50)
    print(" 📊 REPORTE DE SESGO DE SELECCIÓN Y RENDIMIENTO")
    print("="*50)
    
    if total_games > 0:
        rejection_rate = (rejected_games / total_games) * 100
        print(f" 🛑 Tasa de Rechazo (Gates): {rejection_rate:.1f}% ({rejected_games}/{total_games} juegos)")
        
        if rejected_games > 0:
            naive_home_win_rate = (rejected_home_wins / rejected_games) * 100
            print(f" 🏠 Win% Local (Rechazados): {naive_home_win_rate:.1f}% (Baseline del mercado ruidoso)")
        
        print("-" * 50)
        
        if total_processed > 0:
            accuracy = (correct_predictions / total_processed) * 100
            print(f" 🎯 ACCURACY (Solo Aceptados): {accuracy:.2f}% ({correct_predictions}/{total_processed})")
            print("\n ⚠️ NOTA: Este Accuracy excluye los juegos más volátiles.")
    else:
        print("⚠️ No se procesaron juegos.")

if __name__ == "__main__":
    run_backtest()