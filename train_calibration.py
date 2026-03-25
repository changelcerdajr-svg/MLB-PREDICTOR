# train_calibration.py
# V12.0: Entrenamiento del Calibrador sin Fuga de Datos (Out-of-Sample)

from model import MLBPredictor
from datetime import datetime, timedelta
from sklearn.isotonic import IsotonicRegression
import pickle
import numpy as np
import sys

# VENTANA DE CALIBRACIÓN ESTRICTA (Separada del Backtest)
TRAIN_START = "2024-04-01"
TRAIN_END = "2024-05-31" 

def train_isotonic_calibrator():
    print("Iniciando recopilación de datos históricos puros (V12.0)...")
    
    # IMPORTANTE: Apagamos el calibrador para entrenar sobre probabilidades crudas
    predictor = MLBPredictor(use_calibrator=False) 
    loader = predictor.loader
    
    current_date = datetime.strptime(TRAIN_START, "%Y-%m-%d")
    end_date = datetime.strptime(TRAIN_END, "%Y-%m-%d")
    
    X_raw = []
    y_real = []
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        games = loader.get_schedule(date_str)
        
        if games:
            for game in games:
                if game['status'] not in ['Final', 'Game Over', 'Completed']: continue
                try:
                    res = predictor.predict_game(game)
                    if 'error' in res: continue 
                    
                    home_prob = res['home_prob']
                    home_won = 1 if game['real_winner'] == game['home_name'] else 0
                    
                    X_raw.append(home_prob)
                    y_real.append(home_won)
                except: pass
        
        sys.stdout.write(f"\rEntrenando: {date_str} | Muestras válidas: {len(X_raw)}")
        sys.stdout.flush()
        current_date += timedelta(days=1)
        
    print("\nAjustando Regresión Isotónica...")
    if len(X_raw) > 300: 
        iso_reg = IsotonicRegression(out_of_bounds='clip')
        iso_reg.fit(X_raw, y_real)
        
        with open('isotonic_calibrator.pkl', 'wb') as f:
            pickle.dump(iso_reg, f)
        print("Calibrador V12.0 guardado con éxito (isotonic_calibrator.pkl).")
    else:
        print("Error: Muestra demasiado pequeña. Amplía el rango de fechas.")

if __name__ == "__main__":
    train_isotonic_calibrator()