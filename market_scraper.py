# market_scraper.py
import requests
import streamlit as st

@st.cache_data(ttl=300) # Guarda el dato por 5 minutos para evitar baneos de IP
def get_live_market_odds():
    """
    Intercepta las líneas de cierre en vivo desde la API pública de ESPN.
    Retorna un diccionario indexado por el nombre del equipo local.
    """
    url = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    odds_dict = {}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            return odds_dict
            
        data = response.json()
        
        for event in data.get('events', []):
            comp = event['competitions'][0]
            
            # Extraemos el equipo local y lo pasamos a minúsculas para un cruce perfecto
            home_team_raw = comp['competitors'][0]['team']['displayName'].lower()
            
            # Buscamos el bloque de momios
            if 'odds' in comp and len(comp['odds']) > 0:
                odds = comp['odds'][0]
                
                # ESPN nos da el Moneyline (ML)
                home_ml = odds.get('homeTeamOdds', {}).get('moneyLine')
                away_ml = odds.get('awayTeamOdds', {}).get('moneyLine')
                
                if home_ml is not None and away_ml is not None:
                    odds_dict[home_team_raw] = {
                        'home_ml': int(home_ml),
                        'away_ml': int(away_ml)
                    }
                    
        return odds_dict
        
    except Exception as e:
        # Si no hay internet o la API cambia, regresamos vacío para no romper la App
        return {}