# market_scraper.py
# Scraper Institucional V12.3 - Captura de Momios en Vivo (ESPN)

import requests
import streamlit as st

# Diccionario de traducción: ESPN a veces usa nombres cortos o variaciones
TEAM_TRANSLATOR = {
    "ny yankees": "new york yankees",
    "ny mets": "new york mets",
    "la dodgers": "los angeles dodgers",
    "la angels": "los angeles angels",
    "chi cubs": "chicago cubs",
    "chi white sox": "chicago white sox",
    "tb rays": "tampa bay rays",
    "wsh nationals": "washington nationals",
    "sf giants": "san francisco giants",
    "sd padres": "san diego padres",
    "stl cardinals": "st. louis cardinals",
    "kc royals": "kansas city royals",
    "az diamondbacks": "arizona diamondbacks",
    "tex rangers": "texas rangers",
    "sea mariners": "seattle mariners",
    "col rockies": "colorado rockies",
    "atl braves": "atlanta braves",
    "bal orioles": "baltimore orioles"
}

@st.cache_data(ttl=120) # Actualizamos cada 2 minutos en lugar de 5
def get_live_market_odds():
    """
    Intercepta las líneas de cierre en vivo desde la API pública de ESPN.
    Clasifica estrictamente por Equipo Local para sincronizar con la app.
    """
    url = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    odds_dict = {}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            return odds_dict
            
        data = response.json()
        
        for event in data.get('events', []):
            comp = event['competitions'][0]
            
            home_name_raw = ""
            away_name_raw = ""
            
            # 1. Búsqueda estricta de local vs visitante
            for competitor in comp.get('competitors', []):
                team_name = competitor['team']['displayName'].lower()
                if competitor.get('homeAway') == 'home':
                    home_name_raw = team_name
                else:
                    away_name_raw = team_name
            
            # 2. Traducción al formato oficial MLB
            official_home = TEAM_TRANSLATOR.get(home_name_raw, home_name_raw)
            
            # 3. Extracción de Líneas
            if 'odds' in comp and len(comp['odds']) > 0:
                odds = comp['odds'][0]
                home_ml = odds.get('homeTeamOdds', {}).get('moneyLine')
                away_ml = odds.get('awayTeamOdds', {}).get('moneyLine')
                
                # ESPN a veces manda las líneas cerradas (None) o en otro formato si el juego ya empezó
                if home_ml is not None and away_ml is not None:
                    # Indexamos usando el equipo LOCAL
                    odds_dict[official_home] = {
                        'home_ml': int(home_ml),
                        'away_ml': int(away_ml)
                    }
                    
        return odds_dict
    except Exception as e:
        # st.sidebar.error(f"Error interno del Scraper: {e}") # Descomenta para debugguear
        return {}