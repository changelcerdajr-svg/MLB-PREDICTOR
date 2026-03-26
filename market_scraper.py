# market_scraper.py
import requests
import streamlit as st

# Diccionario de traducción: [Nombre ESPN en minúsculas] -> [Nombre Oficial MLB en minúsculas]
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
    "az diamondbacks": "arizona diamondbacks"
}

@st.cache_data(ttl=300)
def get_live_market_odds():
    """
    Intercepta las líneas de cierre en vivo desde la API pública de ESPN
    y traduce los nombres al formato oficial de la API de MLB.
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
            
            # 1. Extraemos el nombre crudo de ESPN
            espn_name = comp['competitors'][0]['team']['displayName'].lower()
            
            # 2. Lo traducimos al nombre oficial de MLB (o lo dejamos igual si no está en la lista)
            official_name = TEAM_TRANSLATOR.get(espn_name, espn_name)
            
            if 'odds' in comp and len(comp['odds']) > 0:
                odds = comp['odds'][0]
                home_ml = odds.get('homeTeamOdds', {}).get('moneyLine')
                away_ml = odds.get('awayTeamOdds', {}).get('moneyLine')
                
                if home_ml is not None and away_ml is not None:
                    # Guardamos el momio indexado por el nombre oficial de MLB
                    odds_dict[official_name] = {
                        'home_ml': int(home_ml),
                        'away_ml': int(away_ml)
                    }
                    
        return odds_dict
    except Exception as e:
        return {}