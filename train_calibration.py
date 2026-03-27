# train_calibration.py - V17.0 (Sincronizado con Statcast)
from model import MLBPredictor
from datetime import datetime, timedelta
from sklearn.isotonic import IsotonicRegression
import pickle
import os

def train_isotonic_calibrator():
    # CAMBIO CLAVE: Usamos una ventana real de la temporada 2025
    # Agosto y Septiembre son los mejores meses para calibrar (datos más estables)
    TRAIN_START = "2025-08-01"
    TRAIN_END = "2025-09-15"
    
    print("="*60)
    print(f"🛰️ CALIBRANDO MOTOR CON TEMPORADA 2025: {TRAIN_START} al {TRAIN_END}")
    print("="*60)
    
    predictor = MLBPredictor(use_calibrator=False) 
    loader = predictor.loader
    loader._force_historical_mode = True 
    
    current_date = datetime.strptime(TRAIN_START, "%Y-%m-%d")
    end_date = datetime.strptime(TRAIN_END, "%Y-%m-%d")
    
    X_raw, y_real = [], []
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        print(f"📅 Procesando: {date_str}", end=" ", flush=True)
        
        games = loader.get_schedule(date_str)
        if not games:
            print("[-] Sin juegos")
        else:
            count = 0
            for game in games:
                if game['status'] == 'Final':
                    try:
                        res = predictor.predict_game(game)
                        if 'error' in res: continue
                        
                        # Guardamos la probabilidad vs el resultado real
                        X_raw.append(res['home_prob'])
                        y_real.append(1 if game['real_winner'] == game['home_name'] else 0)
                        count += 1
                    except: continue
            print(f"OK ({count} juegos)")
        
        current_date += timedelta(days=1)
        
    if len(X_raw) > 50:
        print(f"\n🔧 Entrenando con {len(X_raw)} muestras...")
        iso_reg = IsotonicRegression(out_of_bounds='clip')
        iso_reg.fit(X_raw, y_real)
        
        with open('isotonic_calibrator.pkl', 'wb') as f:
            pickle.dump(iso_reg, f)
        print("✅ ¡Calibrador V17.0 guardado con éxito!")
    else:
        print("\n❌ Error: No hay suficientes datos en este rango.")

if __name__ == "__main__":
    train_isotonic_calibrator()