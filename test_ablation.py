import numpy as np
from backtest_master import run_master_backtest

# --- PARÁMETROS DEL EXPERIMENTO ---
FECHA_INICIO = "2024-05-01" 
DIAS_PRUEBA = 15

def calcular_brier_score(y_true, y_prob):
    if not y_true or len(y_true) == 0: return 1.0
    return np.mean((np.array(y_prob) - np.array(y_true))**2)

def ejecutar_aislamiento_hothand():
    print("\n" + "="*60)
    print("🔬 PRUEBA DE SENSIBILIDAD: AISLANDO 'HOT HAND'")
    print("="*60)

    # ESCENARIO A: MODELO COMPLETO (Con Racha Reciente)
    print("\n[EJECUTANDO] Escenario A: Modelo Completo (Con Hot Hand)")
    res_full = run_master_backtest(
        FECHA_INICIO, 
        days=DIAS_PRUEBA, 
        use_hot_hand=True, # <--- Racha ACTIVADA
        experiments={'jetlag': True, 'weather': True, 'trajectory': True, 'markov': True}
    )
    brier_full = calcular_brier_score(res_full['y_true'], res_full['y_prob'])

    # ESCENARIO B: MODELO SIN HOT HAND (Talento Base)
    print("\n" + "-"*60)
    print("[EJECUTANDO] Escenario B: Modelo Completo MINUS Hot Hand")
    res_no_hh = run_master_backtest(
        FECHA_INICIO, 
        days=DIAS_PRUEBA, 
        use_hot_hand=False, # <--- Racha DESACTIVADA
        experiments={'jetlag': True, 'weather': True, 'trajectory': True, 'markov': True}
    )
    brier_no_hh = calcular_brier_score(res_no_hh['y_true'], res_no_hh['y_prob'])

    # --- ANÁLISIS DE IMPACTO ---
    impacto = brier_no_hh - brier_full
    
    print("\n" + "!"*60)
    print("📊 REPORTE DE SENSIBILIDAD (HOT HAND)")
    print(f" Brier Modelo Completo:    {brier_full:.4f}")
    print(f" Brier Sin Hot Hand:       {brier_no_hh:.4f}")
    print(f" IMPACTO MARGINAL:         {impacto:+.5f}")
    print("-" * 60)

    if impacto < 0:
        print(" ✅ RESULTADO: Quitar el Hot Hand MEJORÓ el Brier Score.")
        print(" CONCLUSIÓN: La racha reciente es RUIDO (Overfitting).")
    else:
        print(" ❌ RESULTADO: Quitar el Hot Hand EMPEORÓ el Brier Score.")
        print(" CONCLUSIÓN: El Hot Hand captura una tendencia real de rendimiento.")
    print("!"*60 + "\n")

if __name__ == "__main__":
    ejecutar_aislamiento_hothand()