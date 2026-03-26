# market_scraper.py
# Scraper Institucional V13.0 - Integración Directa con The Odds API

import requests
import streamlit as st

# INSERTA TU LLAVE AQUÍ
API_KEY = "0b67fd82591c01def9fa987b4d827f04"

# The Odds API ya entrega los nombres casi perfectos, 
# pero mantenemos un mini-diccionario por seguridad en variaciones mínimas.
TEAM_TRANSLATOR = {
    "chicago white sox": "chicago white sox",
    "chicago cubs": "chicago cubs",
    "new york yankees": "new york yankees",
    "new york mets": "new york mets",
    "los angeles dodgers": "los angeles dodgers",
    "los angeles angels": "los angeles angels"
}

@st.cache_data(ttl=120)
def get_live_market_odds():
    url = f"https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/"
    params = {
        'apiKey': API_KEY,
        'regions': 'us',
        'markets': 'h2h', # Head to Head (Moneyline)
        'oddsFormat': 'american'
    }
    
    odds_dict = {}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            st.sidebar.error(f"Error de conexión: Código {response.status_code}")
            return odds_dict
            
        data = response.json()
        juegos_totales = len(data)
        juegos_con_momios = 0
        
        for game in data:
            home_team = game.get('home_team', '').lower()
            away_team = game.get('away_team', '').lower()
            
            official_home = TEAM_TRANSLATOR.get(home_team, home_team)
            
            # Buscamos la primera casa de apuestas disponible (ej. DraftKings, FanDuel)
            if 'bookmakers' in game and len(game['bookmakers']) > 0:
                # Tomamos la primera casa para la línea de consenso
                bookmaker = game['bookmakers'][0] 
                
                if 'markets' in bookmaker and len(bookmaker['markets']) > 0:
                    outcomes = bookmaker['markets'][0].get('outcomes', [])
                    
                    home_ml = None
                    away_ml = None
                    
                    for outcome in outcomes:
                        team_name = outcome.get('name', '').lower()
                        price = outcome.get('price')
                        
                        if team_name == home_team:
                            home_ml = price
                        elif team_name == away_team:
                            away_ml = price
                            
                    if home_ml is not None and away_ml is not None:
                        odds_dict[official_home] = {
                            'home_ml': int(home_ml),
                            'away_ml': int(away_ml)
                        }
                        juegos_con_momios += 1

        # Panel de Diagnóstico en la Interfaz
        st.sidebar.markdown("---")
        st.sidebar.markdown("### Radar de Mercado (The Odds API)")
        st.sidebar.write(f"Juegos en pizarra: {juegos_totales}")
        
        if juegos_con_momios == 0:
            st.sidebar.warning("Las casas de apuestas aún no publican líneas de dinero para hoy.")
        else:
            st.sidebar.success(f"Líneas extraídas de Las Vegas: {juegos_con_momios}")
            
        return odds_dict

    except Exception as e:
        st.sidebar.error("Fallo crítico en el motor de extracción de momios.")
        return {}