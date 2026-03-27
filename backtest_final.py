# backtest_final.py
# Motor de Validación V17.1 (Sincronizado con Statcast + Medición de Alpha Real)

from model import MLBPredictor
import datetime

# --- CONFIGURACIÓN DE RIESGO ---
CONFIDENCE_THRESHOLD = 0.55  # Solo operamos juegos con más de 55% de probabilidad calibrada

def run_backtest(start_date_str, days=5):
    # Usamos el predictor que ya tiene integrado el Scraper y la calibración
    predictor = MLBPredictor(use_calibrator=True) 
    start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
    
    total_games = 0
    actionable_games = 0
    correct = 0
    units_won = 0.0
    home_wins_in_bets = 0 # NUEVO CONTADOR
    
    print("="*60)
    print(f"INICIANDO BACKTEST V17.1: {start_date_str} (+{days} días)")
    print(f"Filtro de Confianza: > {CONFIDENCE_THRESHOLD*100}%")
    print("="*60)

    for i in range(days):
        current_date = (start_date + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        print(f"\n📅 Procesando Fecha: {current_date}")
        
        # El loader ahora usa el año dinámico
        games = predictor.loader.get_schedule(current_date)
        
        for g in games:
            if g['status'] != 'Final': continue
            
            res = predictor.predict_game(g)
            
            # Si hay un error, lo saltamos
            if 'error' in res: continue
            
            total_games += 1
            prediction = res['winner']
            actual_winner = g['real_winner']
            confidence = res.get('confidence', 0.5)

            # --- LA LÓGICA DE WALL STREET: Solo operar si hay Edge ---
            if confidence >= CONFIDENCE_THRESHOLD:
                actionable_games += 1
                is_correct = (prediction == actual_winner)
                
                # Calcular baseline dinámico (Victorias del local)
                if actual_winner == g['home_name']:
                    home_wins_in_bets += 1

                if is_correct:
                    correct += 1
                    units_won += 0.95 # Asumiendo cuota promedio de -105 / 1.95
                else:
                    units_won -= 1.0
                
                print(f"  - {g['away_name']} @ {g['home_name']}: {'✅' if is_correct else '❌'} (Pick: {prediction} | Confianza: {confidence*100:.1f}%)")
            else:
                print(f"  - {g['away_name']} @ {g['home_name']}: ⏭️ No Bet (Confianza: {confidence*100:.1f}%)")

    # --- REPORTE DE RENDIMIENTO INSTITUCIONAL ---
    if total_games > 0:
        print("\n" + "="*60)
        print(f"📊 RESULTADOS DEL BACKTEST OUT-OF-SAMPLE V17.1")
        print("="*60)
        print(f"Juegos Totales Evaluados: {total_games}")
        print(f"💰 JUEGOS OPERADOS (Confianza > {CONFIDENCE_THRESHOLD*100}%): {actionable_games}")
        
        if actionable_games > 0:
            accuracy = (correct / actionable_games) * 100
            roi = (units_won / actionable_games) * 100
            baseline = (home_wins_in_bets / actionable_games) * 100 # NUEVO CÁLCULO
            
            print(f"🎯 ACCURACY EN APUESTAS: {accuracy:.1f}% ({correct}/{actionable_games})")
            print(f"🏠 BASELINE DEL MERCADO (Submuestra): {baseline:.2f}%")
            
            lift = accuracy - baseline
            alpha_signal = "🚀 Señal Alpha Detectada" if lift > 2.5 else "⚠️ Ruido Estadístico"
            print(f"📈 LIFT REAL DEL MODELO: +{lift:.2f}% ({alpha_signal})")
            
            print(f"💵 Ganancia Neta: {units_won:.2f} Unidades")
            print(f"🏦 ROI Estimado: {roi:.1f}%")
        else:
            print("❌ No se encontraron juegos con suficiente confianza para operar.")
        print("="*60)

if __name__ == "__main__":
    # Prueba corriendo finales de Agosto 2024 (Out of sample respecto a la calibración de 2025)
    run_backtest("2024-08-20", days=10)