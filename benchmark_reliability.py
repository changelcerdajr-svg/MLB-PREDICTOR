import numpy as np
from backtest_master import run_master_backtest
from sklearn.metrics import brier_score_loss

def run_reliability_report(start_date="2025-04-01", days=150):
    print(f"📊 Generando Reliability Diagram ({days} días)...")
    
    # Ejecutamos backtest (asegúrate que use_calibrator=True en MLBPredictor dentro del backtest)
    res = run_master_backtest(start_date, days=days, use_hot_hand=False)
    
    if not res or 'y_true' not in res:
        print("No hay datos suficientes para el benchmark.")
        return

    y_true = np.array(res['y_true'])
    y_prob = np.array(res['y_prob'])
    
    print("\nANÁLISIS POR BUCKETS DE CONFIANZA:")
    print(f"{'Rango':<15} | {'Predicho':<10} | {'Real':<10} | {'N':<6} | {'Estatus'}")
    print("-" * 65)

    # Definimos los rangos de interés para apuestas
    buckets = [(0.52, 0.55), (0.55, 0.60), (0.60, 0.65), (0.65, 1.0)]
    
    for low, high in buckets:
        mask = (y_prob >= low) & (y_prob < high)
        n = np.sum(mask)
        
        if n > 5:
            actual_rate = np.mean(y_true[mask])
            pred_rate = np.mean(y_prob[mask])
            diff = pred_rate - actual_rate
            
            status = "✅ OK"
            if diff > 0.03: status = "⚠️ SOBREESTIMADO"
            elif diff < -0.03: status = "⚠️ SUBESTIMADO"
            
            print(f"{low:>3.0%} a {high:>3.0%:<7} | {pred_rate:>10.2%} | {actual_rate:>10.2%} | {n:<6} | {status}")

    total_brier = brier_score_loss(y_true, y_prob)
    print("-" * 65)
    print(f"Brier Score Total: {total_brier:.4f} (Objetivo: < 0.2400)")

if __name__ == "__main__":
    run_reliability_report()