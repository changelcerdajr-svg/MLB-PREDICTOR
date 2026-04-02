# train_calibration.py - V17.9 (Full Audit - Overnight Edition)
from model import MLBPredictor
from datetime import datetime, timedelta
from sklearn.linear_model import LogisticRegression
import numpy as np
from financial import get_fair_prob
import pickle
import json
import os


current_year = datetime.now().year

# --- FUNCIÓN DE APOYO PARA LEER TUS ODDS HISTÓRICOS ---
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
    # ---------------------------------------------------------
    # CONFIGURACIÓN DE ENTRENAMIENTO OVERNIGHT (V17.9)
    # Cierre de temporada 2024 (2 meses de datos ultra-estables)
    # ---------------------------------------------------------
    # ANTES: TRAIN_START = "2025-04-01"


# FIX BUG #7: Entrenamiento dinámico siempre usando la temporada completa del año ANTERIOR
    TRAIN_START = f"{current_year - 1}-04-01"
    TRAIN_END = f"{current_year - 1}-10-01"

    print(f"🚀 INICIANDO AUDITORÍA Y CALIBRACIÓN: {TRAIN_START} al {TRAIN_END}")
    
    predictor = MLBPredictor(use_calibrator=False) 
    X_raw, y_real = [], []
    units_won, bets_count = 0.0, 0

    current_date = datetime.datetime.strptime(TRAIN_START, "%Y-%m-%d")
    end_date = datetime.datetime.strptime(TRAIN_END, "%Y-%m-%d")
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        print(f"🗓️ Procesando juegos del: {date_str}...") # <--- TESTIGO VISUAL
        
        games = predictor.loader.get_schedule(date_str)
        
        for game in games:
            if game['status'] == 'Final':
                try:
                    res = predictor.predict_game(game)
                    h_odds, a_odds = get_historical_odds(date_str, game['home_name'])
                    
                    if h_odds and a_odds:
                        fair_h, fair_a = get_fair_prob(h_odds, a_odds)
                        
                        # 🔴 Seguro temporal para ver si el modelo devolvió un error de lineups
                        if 'error' in res:
                            print(f"  [-] Partido omitido: {res['error']}")
                            continue
                            
                        prob = res['home_prob']
                        edge = prob - fair_h # Edge sobre el precio justo
                        
                        # A2: Entrenamos el calibrador con TODOS los juegos
                        X_raw.append(prob)
                        y_real.append(1 if game['real_winner'] == game['home_name'] else 0)
                        
                        # Solo calculamos el P&L de auditoría si hay edge real
                        if abs(edge) > 0.02:
                            bets_count += 1
                            actual_winner_home = (game['real_winner'] == game['home_name'])
                            pick_is_home = (edge > 0)
                            
                            if (pick_is_home and actual_winner_home) or (not pick_is_home and not actual_winner_home):
                                o = h_odds if pick_is_home else a_odds
                                units_won += (o/100 if o > 0 else 100/abs(o))
                            else:
                                units_won -= 1.0
                    else:
                        print(f"  [-] No encontré momios en el JSON para {game['home_name']}")
                        
                except Exception as e: 
                    # 🔴 EL DETECTOR DE MENTIRAS
                    print(f"  [!] Error oculto al simular {game['away_name']} @ {game['home_name']}: {e}")
                    continue
        current_date += timedelta(days=1)

    # --- RESULTADOS FINALES ---
    # --- RESULTADOS FINALES ---
    print("\n" + "="*50)
    if len(X_raw) > 50:
        # BUG 3 FIX: Prevención de ZeroDivisionError
        roi = (units_won / bets_count) * 100 if bets_count > 0 else 0.0
        
        print(f"RESULTADO FINAL AUDITORÍA V17.9")
        print(f"Muestra evaluada: {bets_count} apuestas")
        print(f"Unidades Netas:   {units_won:+.2f} u")
        print(f"ROI Proyectado:   {roi:+.2f}%") 
        
        # --- FIX MEDIO: PLATT SCALING (REGULARIZACIÓN L2) ---
        X_reshaped = np.array(X_raw).reshape(-1, 1)
        
        # Regresión Logística con penalización C=1.0 para evitar overfitting
        lr = LogisticRegression(C=1.0, penalty='l2', solver='lbfgs')
        lr.fit(X_reshaped, y_real)
        
        # Creamos una clase Wrapper para que model.py siga funcionando igual
        class RegularizedCalibrator:
            def __init__(self, model):
                self.model = model
            def predict(self, X):
                X_arr = np.array(X).reshape(-1, 1)
                # Retornamos la probabilidad calibrada de victoria
                return self.model.predict_proba(X_arr)[:, 1]

        calibrator = RegularizedCalibrator(lr)
        
        with open('isotonic_calibrator.pkl', 'wb') as f:
            pickle.dump(calibrator, f)
        print("✅ Calibrador Suavizado (Platt Scaling) guardado con éxito.")