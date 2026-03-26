# market_scraper.py
# Scraper Institucional V13.1 - Line Shopping & Env Security

import os
import requests
import streamlit as st
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()
API_KEY = os.environ.get("ODDS_API_KEY")

# Traductor Real: Mapea variaciones de The Odds API y ESPN al Canonical Name de MLB
TEAM_TRANSLATOR = {
    "cws": "chicago white sox",
    "white sox": "chicago white sox",
    "chicago white sox": "chicago white sox",
    "cubs": "chicago cubs",
    "chicago cubs": "chicago cubs",
    "yankees": "new york yankees",
    "yanks": "new york yankees",
    "new york yankees": "new york yankees",
    "mets": "new york mets",
    "new york mets": "new york mets",
    "dodgers": "los angeles dodgers",
    "la dodgers": "los angeles dodgers",
    "los angeles dodgers": "los angeles dodgers",
    "angels": "los angeles angels",
    "la angels": "los angeles angels",
    "los angeles angels": "los angeles angels",
    "d-backs": "arizona diamondbacks",
    "diamondbacks": "arizona diamondbacks",
    "arizona diamondbacks": "arizona diamondbacks",
    "red sox": "boston red sox",
    "boston red sox": "boston red sox"
}

@st.cache_data(ttl=120)
def get_live_market_odds():
    if not API_KEY:
        st.sidebar.error("⚠️ Falta ODDS_API_KEY en variables de entorno (.env).")
        return {}

    url = f"https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/"
    params = {
        'apiKey': API_KEY,
        'regions': 'us',
        'markets': 'h2h',
        'oddsFormat': 'american'
    }
    
    odds_dict = {}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            st.sidebar.error(f"Error de conexión API: {response.status_code}")
            return odds_dict
            
        data = response.json()
        juegos_totales = len(data)
        juegos_con_momios = 0
        
        for game in data:
            home_team = game.get('home_team', '').lower()
            away_team = game.get('away_team', '').lower()
            
            official_home = TEAM_TRANSLATOR.get(home_team, home_team)
            
            best_home_ml = -9999
            best_away_ml = -9999
            
            # LINE SHOPPING: Iteramos por TODOS los bookmakers para encontrar la mejor línea
            for bm in game.get('bookmakers', []):
                for market in bm.get('markets', []):
                    for outcome in market.get('outcomes', []):
                        price = outcome.get('price')
                        if outcome['name'].lower() == home_team:
                            if price > best_home_ml:
                                best_home_ml = price
                        elif outcome['name'].lower() == away_team:
                            if price > best_away_ml:
                                best_away_ml = price
                                
            if best_home_ml != -9999 and best_away_ml != -9999:
                odds_dict[official_home] = {
                    'home_ml': int(best_home_ml),
                    'away_ml': int(best_away_ml)
                }
                juegos_con_momios += 1

        st.sidebar.markdown("---")
        st.sidebar.markdown("### Radar de Mercado (Best Odds)")
        st.sidebar.write(f"Juegos en pizarra: {juegos_totales}")
        
        if juegos_con_momios > 0:
            st.sidebar.success(f"Mejores líneas capturadas: {juegos_con_momios}")
        else:
            st.sidebar.warning("No hay líneas disponibles en los bookmakers de US.")
            
        return odds_dict

    except Exception as e:
        return {}