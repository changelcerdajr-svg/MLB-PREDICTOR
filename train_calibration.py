# train_calibration.py - V17.9 (Full Audit - Overnight Edition)
import time 
from model import MLBPredictor
from datetime import datetime, timedelta
from sklearn.linear_model import LogisticRegression
import numpy as np
from financial import get_fair_prob
import pickle
import json
import os

current_year = datetime.now().year

# --- CLASE WRAPPER GLOBAL ---
class RegularizedCalibrator:
    def __init__(self, model):
        self.model = model
    def predict(self, X):
        X_arr = np.array(X).reshape(-1, 1)
        return self.model.predict_proba(X_arr)[:, 1]

# --- FUNCION DE APOYO PARA LEER TUS ODDS HISTORICOS ---
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

def train_isotonic_calibrator():
    # Entrenamiento dinamico usando el ano anterior
    TRAIN_START = f"{current_year - 1}-04-01"
    TRAIN_END = f"{current_year - 1}-05-01"

    print(f"START: INICIANDO AUDITORIA Y CALIBRACION: {TRAIN_START} al {TRAIN_END}")
    
    predictor = MLBPredictor(use_calibrator=False) 
    X_raw, y_real = [], []
    units_won, bets_count = 0.0, 0

    current_date = datetime.strptime(TRAIN_START, "%Y-%m-%d")
    end_date = datetime.strptime(TRAIN_END, "%Y-%m-%d") 

    # AQUI ESTABA EL ERROR: ESTA LINEA SE HABIA BORRADO
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        
        # --- BLINDAJE ANTI-CAIDA DE INTERNET (Con Backoff Exponencial) ---
        MAX_RETRIES = 5
        games = [] 
        
        for attempt in range(MAX_RETRIES):
            try:
                print(f" Procesando juegos del: {date_str}...") 
                games_result = predictor.loader.get_schedule(date_str)
                if games_result is not None:
                    games = games_result
                    break 
            except Exception as e:
                espera = 30 * (attempt + 1) 
                print(f" [!] Error API. Intento {attempt+1}/{MAX_RETRIES}. Esperando {espera}s...")
                time.sleep(espera)
        else:
            print(f" [X] API caida. Saltando el dia {date_str} para evitar cuelgue.")
        # -----------------------------------------------------------------
        
        for game in games:
            if game['status'] == 'Final':
                try:
                    res = predictor.predict_game(game)
                    h_odds, a_odds = get_historical_odds(date_str, game['home_name'])
                    
                    if h_odds and a_odds:
                        fair_h, fair_a = get_fair_prob(h_odds, a_odds)
                        
                        if 'error' in res: continue
                            
                        prob = res['home_prob']
                        edge = prob - fair_h 
                        
                        X_raw.append(prob)
                        y_real.append(1 if game['real_winner'] == game['home_name'] else 0)
                        
                        if abs(edge) > 0.04:
                            bets_count += 1
                            actual_winner_home = (game['real_winner'] == game['home_name'])
                            pick_is_home = (edge > 0)
                            
                            if (pick_is_home and actual_winner_home) or (not pick_is_home and not actual_winner_home):
                                o = h_odds if pick_is_home else a_odds
                                units_won += (o/100 if o > 0 else 100/abs(o))
                            else:
                                units_won -= 1.0
                except: continue
        current_date += timedelta(days=1)

    print("\n" + "="*50)
    if len(X_raw) > 50:
        roi = (units_won / bets_count) * 100 if bets_count > 0 else 0.0
        
        print(f"RESULTADO FINAL AUDITORIA V17.9")
        print(f"Muestra evaluada: {bets_count} apuestas")
        print(f"Unidades Netas:   {units_won:+.2f} u")
        print(f"ROI Proyectado:   {roi:+.2f}%") 
        
        X_reshaped = np.array(X_raw).reshape(-1, 1)
        lr_model = LogisticRegression(C=1.0, penalty='l2', solver='lbfgs')
        lr_model.fit(X_reshaped, y_real)
        
        calibrator_final = RegularizedCalibrator(lr_model)

        with open('isotonic_calibrator.pkl', 'wb') as f:
            pickle.dump(calibrator_final, f)
        
        print("OK: Calibrador regularizado guardado con exito.")
    else:
        print("ERROR: Muestra insuficiente para calibrar.")

if __name__ == "__main__":
    train_isotonic_calibrator()