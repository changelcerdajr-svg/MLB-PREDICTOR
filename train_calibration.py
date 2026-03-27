# train_calibration.py - V17.0 (Sincronizado con Statcast)
from model import MLBPredictor
from datetime import datetime, timedelta
from sklearn.isotonic import IsotonicRegression
import pickle
import os

def train_isotonic_calibrator():
    # Detectamos el año actual
    current_year = datetime.now().year
    
    # Si estamos en pre-temporada (antes de Abril), calibramos con el cierre del año pasado
    if datetime.now().month < 4:
        TRAIN_START = f"{current_year - 1}-08-15"
        TRAIN_END = f"{current_year - 1}-09-30"
    else:
        # Si ya hay temporada, usamos los últimos 30 días
        end_dt = datetime.now() - timedelta(days=1)
        start_dt = end_dt - timedelta(days=30)
        TRAIN_START = start_dt.strftime("%Y-%m-%d")
        TRAIN_END = end_dt.strftime("%Y-%m-%d")

    print(f"🛰️ CALIBRACIÓN AUTOMÁTICA: {TRAIN_START} al {TRAIN_END}")
    
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