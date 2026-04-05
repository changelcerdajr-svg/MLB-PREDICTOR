print("--- TEST: EL SCRIPT SÍ ESTÁ EJECUTÁNDOSE ---")

import time 
import os
import json
import pickle
print("Librerías básicas cargadas...")

import numpy as np
from datetime import datetime, timedelta
print("Numpy y Datetime cargados...")

try:
    from scipy.optimize import minimize_scalar
    from scipy.special import logit, expit
    print("SciPy cargado correctamente...")
except ImportError:
    print("ERROR FATAL: No tienes instalada la librería 'scipy'.")

from sklearn.metrics import brier_score_loss, log_loss
print("Sklearn cargado...")

from model import MLBPredictor
from financial import get_fair_prob
from config import USE_HOT_HAND_GLOBAL
print("Tus módulos locales cargados...")

current_year = datetime.now().year

def get_historical_odds(date_str, home_team_name):
    path = f'data_odds/mlb_odds_dataset.json'
    if not os.path.exists(path): return None, None
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        games = data.get(date_str, [])
        for g in games:
            dk_home = g.get('gameView', {}).get('homeTeam', {}).get('fullName', '').lower()
            if home_team_name.lower() in dk_home:
                ml = g.get('odds', {}).get('moneyline', [])
                for book in ml:
                    if book['sportsbook'] in ['draftkings', 'vegas_consensus']:
                        return book['currentLine']['homeOdds'], book['currentLine']['awayOdds']
    except: pass
    return None, None

def train_temperature_calibrator():
    TRAIN_START = f"{current_year - 1}-03-28"
    TRAIN_END   = f"{current_year - 1}-09-30" 
    
    print(f"START: ENTRENANDO TEMPERATURE SCALING ({TRAIN_START} al {TRAIN_END})")
    
    predictor = MLBPredictor(
        use_calibrator=False, 
        use_hot_hand=USE_HOT_HAND_GLOBAL, 
        experiments={'jetlag': True, 'weather': True, 'trajectory': True, 'markov': True}
    )
    
    X_raw, y_real = [], []
    current_date = datetime.strptime(TRAIN_START, "%Y-%m-%d")
    end_date = datetime.strptime(TRAIN_END, "%Y-%m-%d") 

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        games = predictor.loader.get_schedule(date_str)
        
        if games:
            for game in games:
                if game['status'] == 'Final' and game['real_winner'] is not None:
                    res = predictor.predict_game(game)
                    if 'error' in res: continue
                    
                    X_raw.append(res['home_prob'])
                    y_real.append(1 if game['real_winner'] == game['home_name'] else 0)
                    
        current_date += timedelta(days=1)

    if len(X_raw) < 500:
        print(f"ERROR: Se necesitan mínimo 500 muestras. Se encontraron {len(X_raw)}.")
        return

    split_idx = int(len(X_raw) * 0.85)
    X_train, X_val = np.array(X_raw[:split_idx]), np.array(X_raw[split_idx:])
    y_train, y_val = np.array(y_real[:split_idx]), np.array(y_real[split_idx:])

    # Clipping de seguridad para evitar infinitos matemáticos en logit
    X_train_clip = np.clip(X_train, 1e-6, 1 - 1e-6)
    X_val_clip   = np.clip(X_val,   1e-6, 1 - 1e-6)

    # Función Objetivo para optimizar T
    def nll(T):
        scaled = expit(logit(X_train_clip) / T)
        return log_loss(y_train, scaled)

    result = minimize_scalar(nll, bounds=(0.5, 5.0), method='bounded')
    T_opt = result.x

    preds_val = expit(logit(X_val_clip) / T_opt)
    
    uncal_brier = brier_score_loss(y_val, X_val)
    cal_brier = brier_score_loss(y_val, preds_val)
    cal_logloss = log_loss(y_val, preds_val)
    sharpness = np.std(preds_val)

    print("\n" + "="*50)
    print("REPORTE DE TEMPERATURE SCALING")
    print("="*50)
    print(f"Muestras Totales:  {len(X_raw)} (Train: {len(X_train)} | Val: {len(X_val)})")
    print(f"Parámetro T Óptimo:{T_opt:.4f}")
    print("-" * 50)
    print(f"Brier Score Crudo: {uncal_brier:.4f}")
    print(f"Brier Calibrado:   {cal_brier:.4f}")
    print(f"Log Loss:          {cal_logloss:.4f} (Debería bajar de 0.85)")
    print(f"Sharpness:         {sharpness:.4f} (Ideal > 0.13)")
    
    with open('temperature_calibrator.pkl', 'wb') as f:
        pickle.dump({'T': float(T_opt)}, f)
    print("\nOK: temperature_calibrator.pkl guardado.")

if __name__ == "__main__":
    train_temperature_calibrator()