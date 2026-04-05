# experiments_grid_search.py corregido
import config
from backtest_master import run_master_backtest
import json
from sklearn.metrics import brier_score_loss # <-- Métrica científica

def run_grid_search():
    print("Iniciando Búsqueda en Cuadrícula (Grid Search) - Optimización por Brier Score")
    
    # Grid 3x3: Descartamos los extremos inútiles y nos quedamos con la zona de valor real
    markov_options = [1.03, 1.05, 1.07] 
    extra_options = [1.6, 1.8, 2.0]
    
    best_brier = 1.0 
    best_params = {}
    results_log = []

    # Punto medio: 60 días (Dos meses completos de temporada)
    START_DATE = "2025-05-01" 
    TEST_DAYS = 45

    for mm in markov_options:
        for xi in extra_options:
            print(f"\nEvaluando: Markov={mm}, Extra={xi}")
            
            config.MARKOV_MULTIPLIER = mm
            config.EXTRA_INNING_MULTIPLIER = xi
            
            # FIX ALTO 6: Entrenar con la racha activada, igual que en producción
            res = run_master_backtest(start_date_str=START_DATE, days=TEST_DAYS, use_hot_hand=True)
            
            if res and 'y_true' in res and 'y_prob' in res:
                # Calculamos el Brier Score: (Predicción - Realidad)^2
                current_brier = brier_score_loss(res['y_true'], res['y_prob'])
                
                print(f" > Brier Score: {current_brier:.4f} | ROI: {res['roi']:.2f}%")
                
                results_log.append({
                    'markov': mm,
                    'extra': xi,
                    'brier': current_brier,
                    'roi': res['roi']
                })
                
                # Buscamos MINIMIZAR el Brier Score
                if current_brier < best_brier:
                    best_brier = current_brier
                    best_params = {'markov': mm, 'extra': xi}

    print("\n" + "="*50)
    print("🏆 RESULTADOS CIENTÍFICOS DEL GRID SEARCH")
    print(f"Mejor Configuración: Markov = {best_params.get('markov')} | Extra = {best_params.get('extra')}")
    print(f"Brier Score Optimo: {best_brier:.4f}")
    print("="*50)
    
    with open('grid_search_results.json', 'w') as f:
        json.dump(results_log, f, indent=4)

if __name__ == "__main__":
    run_grid_search()