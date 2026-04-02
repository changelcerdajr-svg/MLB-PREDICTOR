# oos_validation.py
# Framework de Validación Out-of-Sample (Walk-Forward Prueba Ácida)
import datetime
from backtest_master import run_master_backtest

def run_oos_acid_test():
    print("=" * 60)
    print("🧪 PRUEBA DEL ÁCIDO: VALIDACIÓN OUT-OF-SAMPLE (OOS)")
    print("=" * 60)
    print("Lógica: Probaremos si los parámetros estáticos (Park Factors, HFA)")
    print("sobreviven a un período de tiempo que el modelo NUNCA ha visto.\n")

    # 1. Ventana de Entrenamiento (In-Sample)
    # Podemos dejar 2025 para ver cómo se comportaba el año pasado
    in_sample_start = "2025-04-01"
    in_sample_days = 60 
    
    # 2. Ventana Ciega (Esta temporada 2026)
    # Aquí ponemos la fecha de inicio de esta temporada
    oos_start = "2026-03-25" 
    oos_days = 8 # Los 8 días que mencionaste
    
    print(f"📦 ENTRENAMIENTO / IN-SAMPLE: {in_sample_start} ({in_sample_days} días)")
    results_is = run_master_backtest(in_sample_start, days=in_sample_days, use_hot_hand=True)
    
    print(f"\n🚀 PRUEBA CIEGA / OUT-OF-SAMPLE: {oos_start} ({oos_days} días)")
    results_oos = run_master_backtest(oos_start, days=oos_days, use_hot_hand=True)
    
    print("\n" + "=" * 60)
    print("⚖️ VEREDICTO DE SOBREAJUSTE (OVERFITTING)")
    print("=" * 60)
    
    if results_is and results_oos:
        roi_is = results_is.get('roi', 0)
        roi_oos = results_oos.get('roi', 0)
        edge_is = results_is.get('avg_edge', 0)
        edge_oos = results_oos.get('avg_edge', 0)
        
        print(f"Alpha In-Sample:      {edge_is:+.2f}%  |  ROI In-Sample:      {roi_is:+.2f}%")
        print(f"Alpha Out-of-Sample:  {edge_oos:+.2f}%  |  ROI Out-of-Sample:  {roi_oos:+.2f}%")
        print("-" * 60)
        
        # Evaluación Cuantitativa de la Degradación
        alpha_retention = (edge_oos / edge_is) * 100 if edge_is > 0 else 0
        
        print(f"Retención de Alpha: {alpha_retention:.1f}%")
        if alpha_retention >= 70:
            print("✅ GRADO DE INVERSIÓN: El modelo generaliza de forma excelente. Los parámetros fijos son robustos.")
        elif alpha_retention >= 40:
            print("⚠️ ADVERTENCIA: Hay desgaste de Alpha. Podría haber ligero sobreajuste en Park Factors.")
        else:
            print("❌ FALLO CRÍTICO: El modelo colapsa en datos nuevos. Hiperparámetros sobreajustados.")
    else:
        print("Error: No se completaron ambas pruebas.")
        
if __name__ == "__main__":
    run_oos_acid_test()