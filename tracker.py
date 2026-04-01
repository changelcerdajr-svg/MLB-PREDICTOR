# tracker.py - V17.9 (Sistema de Auditoría y Conciliación Automática)
import pandas as pd
import os

FILE = "history_log.csv"

def init_db():
    """Inicializa la base de datos con las columnas necesarias para el Alpha Real."""
    if not os.path.exists(FILE):
        columns = [
            "Fecha", "Juego", "Pick", "Confianza (%)", 
            "Prob Mercado", "Cuota", "Edge", "Resultado"
        ]
        df = pd.DataFrame(columns=columns)
        df.to_csv(FILE, index=False)

def log_bet(fecha, juego, pick, confianza, prob_mercado, cuota, edge):
    """Registra una nueva operación si no existe previamente."""
    init_db()
    df = pd.read_csv(FILE)
    
    # Evitar duplicados por fecha y juego
    # Evitar duplicados por fecha y juego
    if not ((df['Fecha'] == fecha) & (df['Juego'] == juego)).any():
        new_data = pd.DataFrame([{
            "Fecha": fecha, 
            "Juego": juego, 
            "Pick": pick, 
            "Confianza (%)": round(confianza, 1),
            "Prob Mercado": round(prob_mercado * 100, 1),
            "Cuota": cuota, 
            # --- FIX CRÍTICO #4 ---
            # Guardamos el Edge con su valor real. Eliminamos la multiplicación (* 100)
            "Edge": round(edge, 2),
            "Resultado": "Pendiente"
        }])
        df = pd.concat([df, new_data], ignore_index=True)
        df.to_csv(FILE, index=False)
        return True
    return False

def settle_pending_bets(loader):
    """
    Motor de Cierre: Consulta la API de MLB para actualizar apuestas 'Pendiente'.
    Requiere una instancia de MLBDataLoader para acceder a get_schedule.
    """
    df = load_tracker()
    if df.empty: return
    
    pending_mask = df['Resultado'] == 'Pendiente'
    if not pending_mask.any():
        print("📝 No hay apuestas pendientes por cerrar.")
        return

    for index, row in df[pending_mask].iterrows():
        try:
            # Obtenemos los resultados reales de esa fecha
            games = loader.get_schedule(row['Fecha'])
            for g in games:
                # Sincronización por nombre del equipo local
                if g['status'] == 'Final' and g['home_name'] in row['Juego']:
                    winner = g['real_winner']
                    resultado = "W" if row['Pick'] == winner else "L"
                    df.at[index, 'Resultado'] = resultado
                    print(f"✅ Seteado: {row['Juego']} | Pick: {row['Pick']} | Ganó: {winner} -> {resultado}")
        except Exception as e:
            print(f"⚠️ Error conciliando {row['Juego']}: {e}")
    
    update_tracker(df)

def get_performance_summary():
    """Calcula métricas de rentabilidad real (ROI y Alpha)."""
    df = load_tracker()
    closed_bets = df[df['Resultado'].isin(['W', 'L'])].copy()
    
    if closed_bets.empty:
        return "📊 Sin datos de apuestas cerradas para analizar."

    total = len(closed_bets)
    wins = len(closed_bets[closed_bets['Resultado'] == 'W'])
    
    # Función interna para calcular profit neto por apuesta
    def calc_net_profit(row):
        if row['Resultado'] == 'L': return -1.0
        odds = row['Cuota']
        # Conversión de momio americano a unidades ganadas
        return (odds/100) if odds > 0 else (100/abs(odds))

    profit_units = closed_bets.apply(calc_net_profit, axis=1).sum()
    roi = (profit_units / total) * 100
    alpha_avg = closed_bets['Edge'].mean()

    return {
        "Total Apuestas": total,
        "Win Rate": f"{(wins/total)*100:.1f}%",
        "Net Units": f"{profit_units:+.2f}u",
        "ROI Real": f"{roi:+.2f}%",
        "Alpha Promedio": f"{alpha_avg:+.2f}%"
    }

def load_tracker():
    init_db()
    return pd.read_csv(FILE)

def update_tracker(edited_df):
    edited_df.to_csv(FILE, index=False)

if __name__ == "__main__":
    # Prueba rápida de resumen
    print(get_performance_summary())