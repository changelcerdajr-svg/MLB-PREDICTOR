# hot_hand_updater.py
# Motor de Extracción Asíncrona V18.0 (Capa 2: Sincronización Biomecánica - xwOBAcon)

import os
import json
import datetime
import requests
import pandas as pd
import io

# --- CONFIGURACIÓN ESTRATÉGICA ---
DAYS_BACK = 10
# Ajustado a 10 BBEs (Batted Ball Events). 10 bolas puestas en juego equivalen 
# estadísticamente a unos 15-20 PAs reales, asegurando una muestra con menor varianza.
MIN_EVENTS = 10  
OUTPUT_FILE = 'data_odds/hot_hand.json'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

def update_hot_hand_database(target_date_str=None):
    # Si recibimos una fecha, operamos en Modo Backtest (Viaje en el tiempo)
    if target_date_str:
        end_date = datetime.datetime.strptime(target_date_str, "%Y-%m-%d").date()
    # Si no, operamos en Modo Producción (Hoy)
    else:
        end_date = datetime.date.today() + datetime.timedelta(days=1)
        
    start_date = end_date - datetime.timedelta(days=DAYS_BACK + 1)
    current_year = end_date.year
    
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    
    print(f"   -> Extrayendo ventana móvil: {start_str} al {end_str}")
    
    # FIX: Año hardcodeado dinamizado (hfSea={current_year})
    url = (
        f"https://baseballsavant.mlb.com/statcast_search/csv?all=true"
        f"&type=details&player_type=batter&hfGT=R%7C"
        f"&game_date_gt={start_str}&game_date_lt={end_str}"
        f"&hfSea={current_year}%7C"
    )
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept': 'text/csv',
        'Referer': 'https://baseballsavant.mlb.com/statcast_search'
    }
    
    try:
        print(f"Descargando datos desde {start_str} hasta {end_str}...")
        # AUMENTAMOS TIMEOUT A 90 SEGUNDOS
        response = requests.get(url, headers=headers, timeout=90)
        response.raise_for_status()

        print(f"Status Code: {response.status_code}")
        print(f"Tamaño de respuesta: {len(response.text)} bytes")
        
        # Si el tamaño es muy pequeño (ej. menos de 500 bytes), es un bloqueo
        if len(response.text) < 1000:
            print("⚠️ El servidor entregó un archivo demasiado pequeño. Posible bloqueo de IP o User-Agent.")
        
        df = pd.read_csv(io.StringIO(response.text))
        
        if df.empty:
            print("El dataframe está vacío. (¿Temporada en pausa?)")
            return False
            
        print(f"Se descargaron {len(df)} eventos de Statcast.")
        
        # NOTA METODOLÓGICA (xwOBAcon):
        # Al extraer 'estimated_woba_using_speedangle' y hacer dropna(), estamos filtrando 
        # ponches y BBs. El resultado es Expected wOBA on Contact (xwOBAcon), no xwOBA real.
        # Esto captura puramente la sincronización biomecánica al impactar la bola.
        df['xwoba_event'] = pd.to_numeric(df['estimated_woba_using_speedangle'], errors='coerce')
        df_clean = df.dropna(subset=['xwoba_event'])
        
        grouped = df_clean.groupby('batter').agg(
            recent_xwobacon=('xwoba_event', 'mean'),
            events_count=('xwoba_event', 'count')
        ).reset_index()
        
        valid_hot_hands = grouped[grouped['events_count'] >= MIN_EVENTS]
        
        # FIX MEDIO 10: Inyectar el promedio de liga dinámico en el JSON
        league_avg_xwobacon = round(float(df_clean['xwoba_event'].mean()), 4)
        hot_hand_dict = {'__league_avg__': league_avg_xwobacon}

        for _, row in valid_hot_hands.iterrows():
            player_id = int(row['batter'])
            hot_hand_dict[player_id] = round(row['recent_xwobacon'], 4)
            
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(hot_hand_dict, f, indent=4)
            
        print(f"Éxito: Se actualizó el Hot Hand (xwOBAcon) para {len(hot_hand_dict)} bateadores.")
        return True

    except Exception as e:
        print(f"Error crítico durante la extracción del Hot Hand: {e}")
        return False

if __name__ == "__main__":
    update_hot_hand_database()