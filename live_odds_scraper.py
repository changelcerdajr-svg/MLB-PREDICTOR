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
    
    print(f"Accediendo a VegasInsider ({datetime.datetime.now().strftime('%H:%M')})...")
    
    try:
        response = scraper.get(url)
        if response.status_code != 200:
            print("El servidor bloqueó la conexión.")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        trs = soup.find_all('tr')
        team_rows = [tr for tr in trs if tr.find('td', class_='game-team')]
        
        if not team_rows:
            print("No se encontraron equipos. VegasInsider pudo haber cambiado su diseño nuevamente.")
            return None

        live_data = []
        
        print(f"Se encontraron {len(team_rows) // 2} partidos programados.")
        
        for i in range(0, len(team_rows) - 1, 2):
            away_tr = team_rows[i]
            home_tr = team_rows[i+1]
            
            away_team = away_tr.find('a', class_='team-name').text.strip()
            home_team = home_tr.find('a', class_='team-name').text.strip()
            
            away_odds_cells = away_tr.find_all('td', class_='game-odds')
            home_odds_cells = home_tr.find_all('td', class_='game-odds')
            
            a_odds = None
            h_odds = None
            
            # DraftKings suele ser la columna 4 (indice 3)
            dk_index = 3
            if len(away_odds_cells) > dk_index and len(home_odds_cells) > dk_index:
                a_span = away_odds_cells[dk_index].find('span', class_='data-moneyline')
                h_span = home_odds_cells[dk_index].find('span', class_='data-moneyline')
                
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
        print(f"Error en el procesamiento: {e}")
        return None

if __name__ == "__main__":
    os.makedirs("data_odds", exist_ok=True)
    data = scrape_live_mlb_odds()
    
    if data:
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        final_json = {today: data}
        
        with open("data_odds/live_odds.json", "w", encoding="utf-8") as f:
            json.dump(final_json, f, indent=4)
        print(f"Exito. Se guardaron {len(data)} lineas de momios en data_odds/live_odds.json")