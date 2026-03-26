# market_scraper.py
# Scraper Institucional V12.4 - Con Radar de Diagnóstico

import requests
import streamlit as st

# Diccionario para atrapar variaciones raras de nombres
TEAM_TRANSLATOR = {
    "d-backs": "arizona diamondbacks",
    "diamondbacks": "arizona diamondbacks",
    "yanks": "new york yankees",
    "sox": "boston red sox",
    "white sox": "chicago white sox",
    "cubbies": "chicago cubs"
}

@st.cache_data(ttl=120)
def get_live_market_odds():
    url = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"
    headers = {'User-Agent': 'Mozilla/5.0'}
    odds_dict = {}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            return odds_dict
            
        data = response.json()
        juegos_totales = len(data.get('events', []))
        juegos_con_momios = 0
        
        for event in data.get('events', []):
            comp = event['competitions'][0]
            
            home_name_raw = ""
            for competitor in comp.get('competitors', []):
                if competitor.get('homeAway') == 'home':
                    home_name_raw = competitor['team']['displayName'].lower()
            
            official_home = TEAM_TRANSLATOR.get(home_name_raw, home_name_raw)
            
            # Buscamos la etiqueta de apuestas
            if 'odds' in comp and len(comp['odds']) > 0:
                odds = comp['odds'][0]
                home_ml = odds.get('homeTeamOdds', {}).get('moneyLine')
                away_ml = odds.get('awayTeamOdds', {}).get('moneyLine')
                
                if home_ml is not None and away_ml is not None:
                    odds_dict[official_home] = {
                        'home_ml': int(home_ml),
                        'away_ml': int(away_ml)
                    }
                    juegos_con_momios += 1
        
        # Reporte de diagnóstico en la interfaz
        st.sidebar.markdown("---")
        st.sidebar.markdown("### Radar de Mercado ESPN")
        st.sidebar.write(f"Juegos detectados hoy: {juegos_totales}")
        
        if juegos_con_momios == 0:
            st.sidebar.warning("Aviso: ESPN no está reportando líneas de dinero en este momento. Ingresa los momios manualmente.")
        else:
            st.sidebar.success(f"Líneas capturadas exitosamente: {juegos_con_momios}")
            
        return odds_dict
        
    except Exception as e:
        st.sidebar.error("Fallo de conexión con el servidor de ESPN.")
        return {}