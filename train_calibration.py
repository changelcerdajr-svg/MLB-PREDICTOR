# train_calibration.py - VERSIÓN DE DIAGNÓSTICO FORZADO V12.2
from model import MLBPredictor
from datetime import datetime, timedelta
from sklearn.isotonic import IsotonicRegression
import pickle
import sys

TRAIN_START = "2024-04-01"
TRAIN_END = "2024-05-31"

def train_isotonic_calibrator():
    print("🛰️ Conectando con MLB StatsAPI...")
    
    predictor = MLBPredictor(use_calibrator=False) 
    loader = predictor.loader
    # FORZAMOS EL MODO HISTÓRICO DESDE EL ARRANQUE
    loader._force_historical_mode = True 
    
    current_date = datetime.strptime(TRAIN_START, "%Y-%m-%d")
    end_date = datetime.strptime(TRAIN_END, "%Y-%m-%d")
    
    X_raw, y_real = [], []
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        print(f"\n📅 Revisando fecha: {date_str}")
        
        games = loader.get_schedule(date_str)
        
        if not games:
            print("  [!] No se encontraron juegos en el calendario para esta fecha.")
        else:
            print(f"  [+] Se encontraron {len(games)} juegos. Procesando...")
            for game in games:
                # 1. Verificación de Status
                if game['status'] not in ['Final', 'Game Over', 'Completed', 'F']:
                    continue
                
                print(f"    ⚾ Procesando: {game['away_name']} @ {game['home_name']}...", end=" ")
                
                # 2. Extracción de Marcador (Validación V10.1 / V12.2)
                try:
                    h_score = game['real_score']['home']
                    a_score = game['real_score']['away']
                    if h_score == a_score: 
                        print("SALTADO (Empate)")
                        continue
                        
                    # 3. Predicción
                    res = predictor.predict_game(game)
                    
                    if 'error' in res:
                        print(f"RECHAZADO: {res['error']}")
                        continue
                        
                    X_raw.append(res['home_prob'])
                    y_real.append(1 if h_score > a_score else 0)
                    print("✅ OK")
                    
                except Exception as e:
                    print(f"❌ ERROR: {e}")
        
        current_date += timedelta(days=1)
        print(f"--- Muestras acumuladas: {len(X_raw)} ---")
        
    if len(X_raw) > 5: # Bajamos el límite solo para la prueba de diagnóstico
        print("\n🔧 Ajustando Regresión Isotónica...")
        iso_reg = IsotonicRegression(out_of_bounds='clip')
        iso_reg.fit(X_raw, y_real)
        with open('isotonic_calibrator.pkl', 'wb') as f:
            pickle.dump(iso_reg, f)
        print("✅ Calibrador guardado.")
    else:
        print("\n❌ Error crítico: No se recolectaron suficientes muestras.")

if __name__ == "__main__":
    train_isotonic_calibrator()