# tracker.py
import pandas as pd
import os

FILE = "history_log.csv"

def init_db():
    if not os.path.exists(FILE):
        df = pd.DataFrame(columns=["Fecha", "Juego", "Pick", "Confianza (%)", "Cuota", "Edge", "Resultado"])
        df.to_csv(FILE, index=False)

def log_bet(fecha, juego, pick, confianza, cuota, edge):
    init_db()
    df = pd.read_csv(FILE)
    # Evitar duplicados del mismo juego el mismo día
    if not ((df['Fecha'] == fecha) & (df['Juego'] == juego)).any():
        new_data = pd.DataFrame([{
            "Fecha": fecha, 
            "Juego": juego, 
            "Pick": pick, 
            "Confianza (%)": round(confianza, 1), 
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