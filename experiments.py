# experiments.py
# Motor de Fatiga por Viaje (Jetlag Geográfico Real) - V12.1

import pandas as pd
from datetime import timedelta
import math
from config import STADIUM_COORDS

def haversine(lat1, lon1, lat2, lon2):
    """Calcula la distancia en kilómetros entre dos coordenadas."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return R * 2 * math.asin(math.sqrt(a))

def get_jetlag_index(team_id, current_game_date, schedule_df):
    """
    Calcula el desgaste por viaje basado en la distancia real recorrida
    desde el estadio de ayer hasta el estadio de hoy, SIN día de descanso.
    """
    try:
        current_date = pd.to_datetime(current_game_date)
        yesterday = current_date - timedelta(days=1)
        
        # 1. ¿Dónde jugó ayer?
        yesterday_games = schedule_df[
            (pd.to_datetime(schedule_df['date']) == yesterday) & 
            ((schedule_df['home_team'] == team_id) | (schedule_df['away_team'] == team_id))
        ]
        
        if yesterday_games.empty:
            return 0.0 # Tuvo día de descanso, no hay jetlag
            
        last_game = yesterday_games.iloc[0]
        # El venue (estadio) siempre es el del equipo local
        yesterday_venue = last_game['home_team'] 
        
        # 2. ¿Dónde juega hoy?
        current_games = schedule_df[
            (pd.to_datetime(schedule_df['date']) == current_date) & 
            ((schedule_df['home_team'] == team_id) | (schedule_df['away_team'] == team_id))
        ]
        
        if current_games.empty:
            return 0.0
            
        current_venue = current_games.iloc[0]['home_team']
        
        # 3. Si es la misma ciudad/estadio, no hay viaje
        if yesterday_venue == current_venue:
            return 0.0
            
        # 4. Calcular distancia real
        c1 = STADIUM_COORDS.get(yesterday_venue)
        c2 = STADIUM_COORDS.get(current_venue)
        
        if not c1 or not c2:
            return 0.0 # Faltan coordenadas, asumimos 0 para no romper el modelo
            
        dist_km = haversine(c1['lat'], c1['lon'], c2['lat'], c2['lon'])
        
        # 5. Asignar índice de castigo basado en distancia
        if dist_km > 2000: 
            return 1.0   # Vuelo transcontinental (Ej: NY a LA)
        elif dist_km > 800:  
            return 0.5   # Vuelo regional largo
        else:
            return 0.25  # Vuelo corto en la misma costa
            
    except Exception as e:
        return 0.0

def apply_jetlag_penalty(base_power_score, jetlag_value):
    """
    Aplica el castigo matemático al score ofensivo.
    """
    if jetlag_value == 1.0:
        return base_power_score * 0.98 # -2% poder (Transcontinental)
    elif jetlag_value == 0.5:
        return base_power_score * 0.99 # -1% poder (Regional)
    elif jetlag_value == 0.25:
        return base_power_score * 0.995 # -0.5% poder (Corto)
        
    return base_power_score