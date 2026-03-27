# backtest_final.py
# Motor de Validación V17.0 (Sincronizado con Statcast + Clima Vectorial)

from model import MLBPredictor
import datetime

def run_backtest(start_date_str, days=5):
    # Usamos el predictor que ya tiene integrado el Scraper y la calibración
    predictor = MLBPredictor(use_calibrator=True) 
    start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
    
    total_games = 0
    correct = 0
    units_won = 0.0
    
    print("="*60)
    print(f"INICIANDO BACKTEST V17.0: {start_date_str} (+{days} días)")
    print("="*60)

    for i in range(days):
        current_date = (start_date + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        print(f"\n📅 Procesando Fecha: {current_date}")
        
        # El loader ahora usa el año dinámico (2025/2026)
        games = predictor.loader.get_schedule(current_date)
        
        for g in games:
            if g['status'] != 'Final': continue
            
            res = predictor.predict_game(g)
            
            # Si el lineup no estaba confirmado, el modelo devuelve un error (bloqueo de seguridad)
            if 'error' in res: continue
            
            total_games += 1
            prediction = res['winner']
            actual_winner = g['real_winner']
            
            is_correct = (prediction == actual_winner)
            if is_correct:
                correct += 1
                units_won += 0.95 # Asumiendo cuota promedio de -105 / 1.95
            else:
                units_won -= 1.0
            
            print(f"  - {g['away_name']} @ {g['home_name']}: {'✅' if is_correct else '❌'} (Pick: {prediction})")

    # Reporte de Rendimiento
    if total_games > 0:
        accuracy = (correct / total_games) * 100
        roi = (units_won / total_games) * 100
        print("\n" + "="*60)
        print(f"RESULTADOS FINALES (Arquitectura Statcast V17.0)")
        print(f"Total Juegos: {total_games}")
        print(f"Precisión: {accuracy:.1f}%")
        print(f"Ganancia Neta: {units_won:.2f} Unidades")
        print(f"ROI Estimado: {roi:.1f}%")
        print("="*60)
    else:
        print("\n⚠️ No se encontraron juegos válidos para este periodo.")

if __name__ == "__main__":
    # 18 de julio de 2025: Reinicio de la temporada tras el All-Star
    run_backtest("2025-07-18", days=15)