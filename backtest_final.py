# backtest_final.py
# Auditoría Institucional Out-of-Sample - V12.2
import sys
from datetime import datetime, timedelta
from model import MLBPredictor

# --- CONFIGURACIÓN DEL BACKTEST ---
START_DATE = "2024-07-01"  # FIREWALL TEMPORAL: Estricto Out-of-Sample (post-calibración)
DAYS_TO_TEST = 60          # Tamaño de la muestra (2 meses)

def run_backtest():
    print("="*50)
    print(" 🔬 AUDITORÍA INSTITUCIONAL V12.2 (Out-of-Sample)")
    print(f" 📅 Desde: {START_DATE} | Periodo: {DAYS_TO_TEST} días")
    print("="*50)

    try:
        predictor = MLBPredictor()
    except Exception as e:
        print(f"Error inicializando el motor: {e}")
        return

    current_date = datetime.strptime(START_DATE, "%Y-%m-%d")
    
    # Contadores Maestros
    total_processed = 0
    correct_predictions = 0
    rejected_games = 0
    home_wins_in_accepted = 0  # NUEVO: Contador para el Baseline Dinámico

    for i in range(DAYS_TO_TEST):
        test_date = current_date.strftime("%Y-%m-%d")
        print(f"Procesando: {test_date}...")
        
        try:
            games = predictor.loader.get_schedule(test_date) # LÍNEA CORREGIDA
        except Exception as e:
            print(f"  [!] Error obteniendo juegos: {e}")
            current_date += timedelta(days=1)
            continue
            
        if not games:
            current_date += timedelta(days=1)
            continue

        for game in games:
            # INYECCIÓN: Apagamos validación de lineups vivos para probar datos históricos
            predictor.loader._force_historical_mode = True

            # BUG CORREGIDO: Leemos el marcador real del diccionario correcto
            home_score = game['real_score']['home']
            away_score = game['real_score']['away']
            
            if home_score == away_score:
                continue
                
            real_winner = game['real_winner']
            
            # Ejecutamos la predicción
            res = predictor.predict_game(game)
            
            # La Compuerta de Riesgo (Rechazos)
            if 'error' in res:
                rejected_games += 1
                continue
                
            total_processed += 1
            predicted_winner = res['winner']
            
            # Evaluamos Precisión
            if predicted_winner == real_winner:
                correct_predictions += 1
                
            # Evaluamos el Baseline Real de esta submuestra
            if real_winner == game['home_name']:
                home_wins_in_accepted += 1
                
        # Avanzamos al siguiente día
        current_date += timedelta(days=1)
        
    # --- REPORTE FINAL ---
    total_games = total_processed + rejected_games
    print("\n\n" + "="*50)
    print(" 📊 RESULTADOS OUT-OF-SAMPLE (V12.2)")
    print("="*50)
    
    if total_games > 0:
        rejection_rate = (rejected_games / total_games) * 100
        print(f" 🛑 Tasa de Rechazo (Falta Info): {rejection_rate:.1f}% ({rejected_games}/{total_games})")
        print("-" * 50)
        
        if total_processed > 0:
            accuracy = (correct_predictions / total_processed) * 100
            print(f" 🎯 ACCURACY REAL: {accuracy:.2f}% ({correct_predictions}/{total_processed})")
            
            # CÁLCULO DE LIFT INSTITUCIONAL
            real_baseline = (home_wins_in_accepted / total_processed) * 100
            real_lift = accuracy - real_baseline
            
            print(f" 🏠 BASELINE REAL (Submuestra): {real_baseline:.2f}%")
            print(f" 🚀 LIFT REAL DEL MODELO: {real_lift:+.2f}%")
            
            print("-" * 50)
            if real_lift > 0:
                print(" ✅ SEÑAL DIRECCIONAL CONFIRMADA: El modelo vence la inercia del mercado.")
            else:
                print(" ⚠️ ALERTA: El modelo no supera la heurística de 'apostar siempre al local'.")
        else:
            print(" No hubo juegos aceptados para evaluar.")
    else:
        print(" No se procesó ningún juego en este periodo.")

if __name__ == "__main__":
    run_backtest()