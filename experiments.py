import pandas as pd
from datetime import timedelta

def get_jetlag_index(team_id, current_game_date, schedule_df):
    """
    Detecta fatiga por viaje real.
    Solo penaliza si el equipo jugó ayer y la ubicación de ayer es distinta a la de hoy.
    """
    try:
        import pandas as pd
        from datetime import timedelta
        
        current_date = pd.to_datetime(current_game_date)
        yesterday = current_date - timedelta(days=1)
        
        yesterday_games = schedule_df[
            (pd.to_datetime(schedule_df['date']) == yesterday) & 
            ((schedule_df['home_team'] == team_id) | (schedule_df['away_team'] == team_id))
        ]
        
        if yesterday_games.empty:
            return 0.0 
            
        last_game = yesterday_games.iloc[0]
        last_location = last_game['home_team'] 
        
        # Necesitamos saber si hoy es local o visitante
        # Si el equipo local de ayer no es el mismo que el equipo local de hoy, hubo vuelo.
        current_games = schedule_df[
            (pd.to_datetime(schedule_df['date']) == current_date) & 
            ((schedule_df['home_team'] == team_id) | (schedule_df['away_team'] == team_id))
        ]
        
        if not current_games.empty:
            current_location = current_games.iloc[0]['home_team']
            if last_location != current_location:
                return 1.0 # Hubo viaje real sin día de descanso
                
        return 0.0 # Jugó back-to-back pero en la misma ciudad

    except:
        return 0.0

def apply_jetlag_penalty(base_power_score, jetlag_value):
    """
    Aplica el castigo matemático al score ofensivo.
    """
    if jetlag_value >= 1.0:
        # Castigo fuerte: Reducir 2% el poder ofensivo
        return base_power_score * 0.98
    elif jetlag_value == 0.5:
        # Castigo leve: Reducir 1%
        return base_power_score * 0.99
    
    return base_power_score