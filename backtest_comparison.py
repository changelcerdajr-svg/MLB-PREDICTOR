import pandas as pd
from backtest_master import run_master_backtest

def run_comparative_audit(start_date, days=10):
    print("=== INICIANDO AUDITORÍA COMPARATIVA V18 vs V19 ===")
    
    # Escenario A: Modelo Base (Sin Hot Hand)
    print("\n--- EJECUTANDO ESCENARIO A (CONTROL: SIN HOT HAND) ---")
    results_a = run_master_backtest(start_date, days=days, use_hot_hand=False)
    
    # Escenario B: Modelo Alpha (Con Hot Hand)
    print("\n--- EJECUTANDO ESCENARIO B (ALPHA: CON HOT HAND) ---")
    results_b = run_master_backtest(start_date, days=days, use_hot_hand=True)
    
    # Resumen Comparativo
    print("\n" + "="*40)
    print("📊 REPORTE DE MEJORA ESTRUCTURAL")
    print("="*40)

    # Verificación de integridad de datos para evitar TypeError
    if results_a and results_b:
        # Extraemos valores con seguridad usando .get()
        roi_a = results_a.get('roi', 0)
        roi_b = results_b.get('roi', 0)
        edge_a = results_a.get('avg_edge', 0)
        edge_b = results_b.get('avg_edge', 0)
        win_a = results_a.get('win_rate', 0)
        win_b = results_b.get('win_rate', 0)

        print(f"✅ Escenario A (Base): ROI {roi_a:.2f}% | WinRate {win_a:.1f}% | Avg Edge {edge_a:.2f}%")
        print(f"✅ Escenario B (HotHand): ROI {roi_b:.2f}% | WinRate {win_b:.1f}% | Avg Edge {edge_b:.2f}%")
        print("-" * 40)
        print(f"🚀 DIFERENCIA DE ALPHA (B - A): {edge_b - edge_a:+.2f}%")
        print(f"💰 DIFERENCIA DE RENTABILIDAD: {roi_b - roi_a:+.2f}%")
    else:
        print("\n⚠️ RESULTADOS INCOMPLETOS")
        print("El modelo no encontró suficientes apuestas en uno o ambos escenarios.")
        print("Sugerencia: Abre 'backtest_master.py' y reduce el 'MIN_EDGE' a 0.005 para forzar actividad.")
    
    print("="*40)

if __name__ == "__main__":
    # Puedes poner 1 de julio, 20 días, y el motor hará el resto.
    run_comparative_audit("2025-07-01", days=20)