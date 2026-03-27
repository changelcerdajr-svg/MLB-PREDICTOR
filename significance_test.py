# significance_test.py
import pandas as pd
import numpy as np
from scipy import stats
import os

FILE = "history_log.csv"

def american_to_decimal(odds):
    if odds > 0: return (odds / 100.0) + 1.0
    elif odds < 0: return (100.0 / abs(odds)) + 1.0
    return 1.0

def run_significance_test():
    print("="*60)
    print(" 🔬 AUDITORÍA CUANTITATIVA: BOOTSTRAP CI & BRIER SCORE")
    print("="*60)

    if not os.path.exists(FILE):
        print("❌ No se encontró history_log.csv.")
        return

    df = pd.read_csv(FILE)
    df_closed = df[df['Resultado'].isin(['Ganado', 'Perdido'])].copy()
    n = len(df_closed)
    
    if n < 30:
        print(f"⚠️ Muestra de {n} juegos. Se recomiendan 200+ para validación institucional.")
        if n == 0: return

    # Preparar datos para Brier Score
    df_closed['resultado_binario'] = (df_closed['Resultado'] == 'Ganado').astype(int)
    df_closed['model_prob'] = df_closed['Confianza (%)'] / 100.0
    df_closed['market_prob'] = df_closed['Prob Mercado'] / 100.0
    
    wins = df_closed['resultado_binario'].sum()
    win_rate_real = wins / n
    
    # 1. Brier Score
    brier_model = ((df_closed['model_prob'] - df_closed['resultado_binario'])**2).mean()
    brier_market = ((df_closed['market_prob'] - df_closed['resultado_binario'])**2).mean()
    brier_adv = brier_market - brier_model

    # 2. Bootstrap CI del Win Rate
    boot_rates = []
    np.random.seed(42)
    for _ in range(10000):
        sample = np.random.choice(df_closed['resultado_binario'].values, size=n, replace=True)
        boot_rates.append(sample.mean())
    ci_low, ci_high = np.percentile(boot_rates, [2.5, 97.5])
    
    # 3. ROI
    df_closed['Cuota_Decimal'] = df_closed['Cuota'].apply(american_to_decimal)
    ganancia_bruta = sum((row['Cuota_Decimal'] - 1.0) if row['Resultado'] == 'Ganado' else -1.0 for _, row in df_closed.iterrows())
    roi = (ganancia_bruta / n) * 100

    print(f"📊 MUESTRA EVALUADA: {n} Operaciones")
    print(f"🎯 Win Rate: {win_rate_real*100:.2f}% | ROI: {roi:+.2f}%")
    print("-" * 60)
    print("📉 BRIER SCORE (Menor es mejor):")
    print(f"   Modelo:  {brier_model:.4f}")
    print(f"   Mercado: {brier_market:.4f}")
    if brier_adv > 0:
        print(f"   ✅ Ventaja sobre el Mercado: +{brier_adv:.4f}")
    else:
        print(f"   ⚠️ Mercado más preciso por: {brier_adv:.4f}")
    print("-" * 60)
    print(f"📈 BOOTSTRAP CI (95%): [{ci_low*100:.2f}%, {ci_high*100:.2f}%]")
    print("="*60)

if __name__ == "__main__":
    run_significance_test()