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

# experiments.py - Modulo de Condiciones de Viaje (M1 Fix)

# Mapeo de Team ID a Zona Horaria (0 = Eastern, 1 = Central, 2 = Mountain, 3 = Pacific)
TEAM_TIMEZONES = {
    # AL East & NL East & Algunos Central (EST)
    110: 0, 111: 0, 147: 0, 139: 0, 141: 0, 144: 0, 146: 0, 121: 0, 143: 0, 120: 0, 113: 0, 114: 0, 116: 0, 134: 0,
    # AL Central & NL Central & AL West Texas (CST)
    145: 1, 118: 1, 142: 1, 112: 1, 158: 1, 138: 1, 117: 1, 140: 1,
    # NL West & AL West Montaña (MST)
    115: 2, 109: 2,
    # NL West & AL West Costa (PST)
    108: 3, 133: 3, 136: 3, 119: 3, 135: 3, 137: 3
}

def get_jetlag_index(team_id, game_date, schedule_data):
    """
    Calcula el impacto biológico basado en el cambio de zona horaria real
    entre el juego anterior y el juego de HOY.
    """
    if schedule_data is None or schedule_data.empty:
        return 0.0
        
    # 1. Identificamos en qué ciudad juega el equipo HOY
    today_game = schedule_data[(schedule_data['date'] == game_date) & 
                               ((schedule_data['away_team'] == team_id) | (schedule_data['home_team'] == team_id))]
    
    if today_game.empty:
        return 0.0 # No tenemos registro de que juegue hoy
        
    # La ciudad actual es el estadio del equipo local del juego de hoy
    current_city_id = today_game.iloc[0]['home_team']

    # 2. Filtramos el historial para ver solo juegos ANTERIORES a hoy
    past_games = schedule_data[(pd.to_datetime(schedule_data['date']) < pd.to_datetime(game_date)) & 
                               ((schedule_data['away_team'] == team_id) | (schedule_data['home_team'] == team_id))]
    
    if past_games.empty:
        return 0.0 # Tuvo días de descanso largos o es inicio de temporada
        
    # El último juego antes de hoy
    last_game = past_games.iloc[-1]
    previous_city_id = last_game['home_team']
    
    # 3. Calculamos la diferencia de zonas horarias reales (donde estaba vs donde está)
    tz_prev = TEAM_TIMEZONES.get(previous_city_id, 0)
    tz_curr = TEAM_TIMEZONES.get(current_city_id, 0) # BUG FIX: Usamos la ciudad actual
    
    tz_diff = tz_prev - tz_curr
    
    # Viajar al Este (perder horas) es peor que viajar al Oeste (ganar horas)
    if tz_diff > 0:
        return abs(tz_diff) * 1.5
    elif tz_diff < 0:
        return abs(tz_diff) * 0.8
    else:
        return 0.0

def apply_jetlag_penalty(base_score, jetlag_index):
    """
    Reduce el base_score (carreras esperadas) basado en el Jet Lag cognitivo.
    """
    # Castigo máximo de ~4.5% para un viaje de 3 zonas al Este sin descanso
    penalty_multiplier = max(0.95, 1.0 - (jetlag_index * 0.01))
    return base_score * penalty_multiplier