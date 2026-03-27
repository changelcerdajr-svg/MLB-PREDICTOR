# tracker.py
import pandas as pd
import os

FILE = "history_log.csv"

def init_db():
    if not os.path.exists(FILE):
        # AÑADIMOS LA COLUMNA "Prob Mercado"
        df = pd.DataFrame(columns=["Fecha", "Juego", "Pick", "Confianza (%)", "Prob Mercado", "Cuota", "Edge", "Resultado"])
        df.to_csv(FILE, index=False)

def log_bet(fecha, juego, pick, confianza, prob_mercado, cuota, edge):
    init_db()
    df = pd.read_csv(FILE)
    if not ((df['Fecha'] == fecha) & (df['Juego'] == juego)).any():
        new_data = pd.DataFrame([{
            "Fecha": fecha, 
            "Juego": juego, 
            "Pick": pick, 
            "Confianza (%)": round(confianza, 1),
            "Prob Mercado": round(prob_mercado * 100, 1), # NUEVO
            "Cuota": cuota, 
            "Edge": edge,
            "Resultado": "Pendiente"
        }])
        df = pd.concat([df, new_data], ignore_index=True)
        df.to_csv(FILE, index=False)
        return True
    return False

def load_tracker():
    init_db()
    return pd.read_csv(FILE)

def update_tracker(edited_df):
    edited_df.to_csv(FILE, index=False)