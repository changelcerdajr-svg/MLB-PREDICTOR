# backtest_comparison.py
from backtest_master import run_master_backtest
from statsmodels.stats.proportion import proportions_ztest

def run_comparative_audit(start_date="2025-04-01", days=175):
    print(f"🔬 INICIANDO AUDITORÍA COMPARATIVA ESTADÍSTICA ({days} días)")
    print("El objetivo es probar si la Capa 2 (Hot Hand) genera una mejora real o azarosa.\n")

    print("--- ESCENARIO A: Modelo Estructural Puro (Hot Hand OFF) ---")
    res_A = run_master_backtest(start_date, days=days, use_hot_hand=False)
    
    print("\n--- ESCENARIO B: Modelo Dinámico (Hot Hand ON al 5%) ---")
    res_B = run_master_backtest(start_date, days=days, use_hot_hand=True)

    if res_A and res_B:
        won_A, bets_A = int(res_A['win_rate'] * res_A['bets'] / 100), res_A['bets']
        won_B, bets_B = int(res_B['win_rate'] * res_B['bets'] / 100), res_B['bets']

        print("\n" + "="*50)
        print("⚖️ PRUEBA DE SIGNIFICANCIA ESTADÍSTICA (Z-Test)")
        print("="*50)
        print(f"Modelo Puro:     {res_A['win_rate']:.2f}% ({won_A}/{bets_A} picks) | ROI: {res_A['roi']:.2f}%")
        print(f"Modelo Dinámico: {res_B['win_rate']:.2f}% ({won_B}/{bets_B} picks) | ROI: {res_B['roi']:.2f}%")
        
        # Test de proporciones (para ver si la diferencia es real o suerte)
        count = [won_A, won_B]
        nobs = [bets_A, bets_B]
        stat, pval = proportions_ztest(count, nobs)
        
        print("-" * 50)
        print(f"Diferencia P-Value: {pval:.4f}")
        if pval < 0.05:
            print("✅ CONCLUSIÓN: La diferencia ES estadísticamente significativa.")
        else:
            print("⚠️ CONCLUSIÓN: La diferencia NO supera el ruido estadístico. (Se requiere más muestra).")

if __name__ == "__main__":
    run_comparative_audit()