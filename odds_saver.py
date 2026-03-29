# odds_saver.py
from market_scraper import get_live_market_odds
import json
import datetime
import os

def save_todays_odds():
    print("Obteniendo cuotas estables desde The Odds API...")
    odds = get_live_market_odds() 
    
    if not odds:
        print("Error: No se pudieron obtener las cuotas. Revisa tu API Key o límites.")
        return

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    os.makedirs("data_odds", exist_ok=True)
    
    # Lo guardamos con el nombre que espera tu Terminal de Operaciones
    filepath = "data_odds/live_odds.json" 
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({today: odds}, f, indent=4)
    
    print(f"Éxito: Cuotas de mercado guardadas en {filepath}")

if __name__ == "__main__":
    save_todays_odds()