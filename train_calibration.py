# train_calibration.py
# Laboratorio Cuantitativo: Regresión Isotónica V11.5 (Aislado)

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
import pickle
import os
from datetime import datetime, timedelta
from model import MLBPredictor

def collect_historical_data(start_date="2024-04-15", days=60):
    """
    Corre el modelo hacia atrás para recolectar predicciones CRUDAS.
    """
    print(f"📊 Recolectando {days} días de historia (Datos Crudos)...")
    
    # CRÍTICO: use_calibrator=False evita la fuga de datos (Data Leakage)
    predictor = MLBPredictor(use_calibrator=False)
    loader = predictor.loader
    
    current_date = datetime.strptime(start_date, "%Y-%m-%d")
    results = []
    
    for _ in range(days):
        date_str = current_date.strftime("%Y-%m-%d")
        games = loader.get_schedule(date_str)
        
        if games:
            for game in games:
                if game['status'] not in ['Final', 'Game Over', 'Completed']: continue
                
                try:
                    pred = predictor.predict_game(game)
                    
                    # Compuerta de Seguridad: Si el modelo abortó, ignoramos este juego
                    if 'error' in pred:
                        continue
                    
                    # Estandarizamos la probabilidad siempre hacia el equipo LOCAL
                    is_home_pick = (pred['winner'] == game['home_name'])
                    raw_home_prob = pred['confidence'] if is_home_pick else (1.0 - pred['confidence'])
                    actual_home_win = 1 if game['real_winner'] == game['home_name'] else 0
                    
                    results.append({
                        'raw_prob': raw_home_prob,
                        'actual_win': actual_home_win
                    })
                except Exception as e:
                    pass
                    
        current_date += timedelta(days=1)
        print(f"  ↳ {date_str} procesado. Muestras válidas: {len(results)}")
        
    return pd.DataFrame(results)

def train_isotonic_calibrator():
    # Recolectamos 45 días, suficientes para trazar una curva monótona
    df = collect_historical_data(start_date="2024-05-01", days=45) 
    
    if len(df) < 100:
        print("❌ No hay suficientes datos limpios para entrenar.")
        return
        
    print(f"\n🧠 Entrenando Regresión Isotónica con {len(df)} juegos válidos...")
    
    X = df['raw_prob'].values
    y = df['actual_win'].values
    
    # Entrenamos la calibración con recortes para evitar certezas absolutas
    ir = IsotonicRegression(out_of_bounds='clip', y_min=0.01, y_max=0.99)
    ir.fit(X, y)
    
    # Guardamos el cerebro corrector
    with open('isotonic_calibrator.pkl', 'wb') as f:
        pickle.dump(ir, f)
        
    print("✅ Calibrador empírico guardado exitosamente como 'isotonic_calibrator.pkl'")
    
    # Prueba de cordura
    test_probs = [0.45, 0.50, 0.55, 0.60, 0.65]
    calibrated = ir.predict(test_probs)
    print("\n🔍 Muestra de Calibración (Perspectiva Equipo Local):")
    for raw, cal in zip(test_probs, calibrated):
        print(f"   Crudo: {raw*100:.1f}%  ->  Calibrado: {cal*100:.1f}%")

if __name__ == "__main__":
    train_isotonic_calibrator()