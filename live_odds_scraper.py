# live_odds_scraper.py - V17.9 (Búsqueda Dinámica de Columnas)
import cloudscraper
from bs4 import BeautifulSoup
import json
import datetime
import os

def parse_odds(text):
    text = text.strip().lower()
    if not text or text == 'n/a': return None
    if text == 'even': return 100
    try:
        return int(text.replace('+', ''))
    except ValueError:
        return None

def scrape_live_mlb_odds():
    scraper = cloudscraper.create_scraper()
    url = "https://www.vegasinsider.com/mlb/odds/las-vegas/"
    
    try:
        response = scraper.get(url)
        if response.status_code != 200: return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        trs = soup.find_all('tr')
        team_rows = [tr for tr in trs if tr.find('td', class_='game-team')]
        
        if not team_rows: return None

        live_data = []
        
        # --- NUEVA LÓGICA DE BÚSQUEDA DINÁMICA (PUNTO 10 AUDITORÍA) ---
        header_cells = soup.find_all('th', class_='game-odds')
        dk_index = -1
        for idx, th in enumerate(header_cells):
            if 'draftkings' in th.text.lower():
                dk_index = idx
                break
        
        # Fallback a la columna 3 si la búsqueda falla por nombre
        target_idx = dk_index if dk_index != -1 else 3
        # -------------------------------------------------------------

        for i in range(0, len(team_rows) - 1, 2):
            away_tr = team_rows[i]
            home_tr = team_rows[i+1]
            
            away_team = away_tr.find('a', class_='team-name').text.strip()
            home_team = home_tr.find('a', class_='team-name').text.strip()
            
            away_odds_cells = away_tr.find_all('td', class_='game-odds')
            home_odds_cells = home_tr.find_all('td', class_='game-odds')
            
            a_odds, h_odds = None, None

            # --- APLICACIÓN DEL ÍNDICE DINÁMICO ---
            if len(away_odds_cells) > target_idx and len(home_odds_cells) > target_idx:
                a_span = away_odds_cells[target_idx].find(attrs={"data-moneyline": True})
                h_span = home_odds_cells[target_idx].find(attrs={"data-moneyline": True})
                
                if a_span: a_odds = parse_odds(a_span.text)
                if h_span: h_odds = parse_odds(h_span.text)
            
            if a_odds is not None and h_odds is not None:
                live_data.append({
                    "gameView": {
                        "homeTeam": {"fullName": home_team},
                        "awayTeam": {"fullName": away_team}
                    },
                    "odds": {
                        "moneyline": [
                            {
                                "sportsbook": "draftkings",
                                "currentLine": {"homeOdds": h_odds, "awayOdds": a_odds}
                            }
                        ]
                    }
                })
        
        return live_data
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    os.makedirs("data_odds", exist_ok=True)
    data = scrape_live_mlb_odds()
    if data:
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        with open("data_odds/live_odds.json", "w", encoding="utf-8") as f:
            json.dump({today: data}, f, indent=4)
        print(f"💰 Éxito: {len(data)} juegos registrados.")