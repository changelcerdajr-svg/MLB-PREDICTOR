# check_calibration.py
# Herramienta de Diagnóstico: Curva de Calibración
# Verifica si la "Confianza" del modelo coincide con la "Realidad"

from model import MLBPredictor
from datetime import datetime, timedelta
import sys

# CONFIGURACIÓN
START_DATE = "2025-06-01" 
GAMES_TO_AUDIT = 600      

def run_calibration():
    print("\n" + "⚖️  "*10)
    print(f"   INICIANDO AUDITORÍA DE CALIBRACIÓN")
    print(f"   Motor: V10.1 (Bayesian + Dynamic)")
    print("⚖️  "*10 + "\n")

    predictor = MLBPredictor()
    loader = predictor.loader
    
    current_date = datetime.strptime(START_DATE, "%Y-%m-%d")
    total_processed = 0
    
    # BUCKETS (Cubetas de Confianza)
    # 50-55%, 55-60%, 60-65%, 65-70%, 70-100%
    buckets = {
        '50-55': {'wins': 0, 'total': 0},
        '55-60': {'wins': 0, 'total': 0},
        '60-65': {'wins': 0, 'total': 0},
        '65-70': {'wins': 0, 'total': 0},
        '70+':   {'wins': 0, 'total': 0}
    }
    
    while total_processed < GAMES_TO_AUDIT:
        date_str = current_date.strftime("%Y-%m-%d")
        games = loader.get_schedule(date_str)
        
        if not games:
            current_date += timedelta(days=1)
            continue

        for game in games:
            if total_processed >= GAMES_TO_AUDIT: break
            if game['status'] not in ['Final', 'Game Over', 'Completed']: continue
            
            try:
                # 1. Predecir
                pred = predictor.predict_game(game)
                conf = pred['confidence'] * 100 # Convertir a % (ej. 58.4)
                
                # 2. Clasificar en Cubeta
                bucket_key = ''
                if 50 <= conf < 55: bucket_key = '50-55'
                elif 55 <= conf < 60: bucket_key = '55-60'
                elif 60 <= conf < 65: bucket_key = '60-65'
                elif 65 <= conf < 70: bucket_key = '65-70'
                elif conf >= 70: bucket_key = '70+'
                
                if bucket_key:
                    buckets[bucket_key]['total'] += 1
                    # 3. Verificar si ganó
                    if pred['winner'] == game['real_winner']:
                        buckets[bucket_key]['wins'] += 1
                
                total_processed += 1
                sys.stdout.write(f"\r🔍 Auditando: {total_processed}/{GAMES_TO_AUDIT}")
                sys.stdout.flush()

            except: pass

        current_date += timedelta(days=1)

    # --- REPORTE FINAL ---
    print("\n\n" + "="*60)
    print(f"📊 REPORTE DE CALIBRACIÓN ({GAMES_TO_AUDIT} Juegos)")
    print("="*60)
    print(f"{'RANGO CONFIANZA':<15} | {'JUEGOS':<8} | {'REALIDAD (Win%)':<15} | {'VEREDICTO'}")
    print("-" * 60)
    
    for key, data in buckets.items():
        total = data['total']
        wins = data['wins']
        
        if total > 0:
            real_pct = (wins / total) * 100
            
            # Análisis de Desviación
            # Queremos que el Real% esté cerca del Rango (ej. en 55-60, queremos ~57.5%)
            mid_point = 0
            if key == '50-55': mid_point = 52.5
            elif key == '55-60': mid_point = 57.5
            elif key == '60-65': mid_point = 62.5
            elif key == '65-70': mid_point = 67.5
            elif key == '70+': mid_point = 75.0
            
            diff = real_pct - mid_point
            
            status = "✅ PERFECTO"
            if diff > 5: status = "⚠️ TIMIDO (Ganan más de lo esperado)"
            elif diff < -5: status = "🚨 ARROGANTE (Pierden más de lo esperado)"
            
            print(f"{key:<15} | {total:<8} | {real_pct:.1f}%          | {status}")
        else:
            print(f"{key:<15} | 0        | N/A             | ---")

if __name__ == "__main__":
    run_calibration()