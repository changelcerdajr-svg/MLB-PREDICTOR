# live_odds_scraper.py - V19.1 (Selenium Nativo - Sin WDM)
import os
import json
import time
import datetime
from bs4 import BeautifulSoup

# Librerías del Tanque Selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
# ELIMINAMOS webdriver_manager porque causó el archivo corrupto en Windows

def parse_odds(text):
    if not text: return None
    text = text.strip().lower()
    if text == 'even': return 100
    if text == 'n/a' or text == '': return None
    try:
        return int(text.replace('+', '').replace(',', ''))
    except ValueError:
        return None

def scrape_live_mlb_odds_selenium():
    print("🚀 Iniciando Motor Selenium (Navegador Fantasma)...")
    
    # 1. Configurar opciones de Chrome para ser "Indetectable"
    options = Options()
    
    # MODO FANTASMA ACTIVADO PARA SERVIDOR
    options.add_argument("--headless=new")
    
    # ESCUDOS ANTI-BOT (Camuflaje para parecer un humano real)
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # ESTABILIDAD Y VENTANA
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    try:
        print("⚙️ Iniciando Chrome (Modo Nativo Selenium 4+)...")
        # Usamos la configuración por defecto. Selenium se encarga del driver silenciosamente.
        driver = webdriver.Chrome(options=options)
    except Exception as e:
        print(f"❌ Error al iniciar Chrome: {e}")
        return None

    url = "https://www.vegasinsider.com/mlb/odds/las-vegas/"
    
    try:
        print("🌐 Navegando a VegasInsider...")
        driver.get(url)
        
        # Ahora el bot solo espera a que cargue la columna de los equipos
        WebDriverWait(driver, 25).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "td.game-team"))
        )
        print("✅ Datos detectados en el DOM. Procediendo al parseo.")
        
        # Extraemos el HTML ya procesado y renderizado
        html = driver.page_source
        driver.quit()
        
        soup = BeautifulSoup(html, 'html.parser')
        
        trs = soup.find_all('tr')
        team_rows = [tr for tr in trs if tr.find('td', class_='game-team')]
        
        if not team_rows: 
            print("❌ No se encontraron las tablas. Cloudflare nos bloqueó o la página no cargó.")
            return None

        live_data = []

        # Recorremos los equipos
        for i in range(0, len(team_rows) - 1, 2):
            away_tr = team_rows[i]
            home_tr = team_rows[i+1]
            
            try:
                away_team = away_tr.find('a', class_='team-name').text.strip()
                home_team = home_tr.find('a', class_='team-name').text.strip()
            except AttributeError:
                continue 
            
            away_odds_cells = away_tr.find_all('td', class_='game-odds')
            home_odds_cells = home_tr.find_all('td', class_='game-odds')
            
            a_odds, h_odds = None, None
            
            a_span = away_tr.find(attrs={"data-moneyline": True})
            h_span = home_tr.find(attrs={"data-moneyline": True})
            
            if a_span and h_span:
                a_odds = parse_odds(a_span.text)
                h_odds = parse_odds(h_span.text)
            elif len(away_odds_cells) > 3:
                a_odds = parse_odds(away_odds_cells[3].text)
                h_odds = parse_odds(home_odds_cells[3].text)
            
            if a_odds is not None and h_odds is not None:
                live_data.append({
                    "gameView": {
                        "homeTeam": {"fullName": home_team},
                        "awayTeam": {"fullName": away_team}
                    },
                    "odds": {
                        "moneyline": [
                            {
                                "sportsbook": "vegas_consensus",
                                "currentLine": {"homeOdds": h_odds, "awayOdds": a_odds}
                            }
                        ]
                    }
                })
        
        return live_data
        
    except Exception:
        print("⚠️ Tiempo de espera agotado o página incompleta.")
        driver.quit()
        return None

if __name__ == "__main__":
    os.makedirs("data_odds", exist_ok=True)
    data = scrape_live_mlb_odds_selenium()
    
    if data:
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # 1. Guardar el archivo temporal del día (Para la App en vivo)
        with open("data_odds/live_odds.json", "w", encoding="utf-8") as f:
            json.dump({today: data}, f, indent=4)
        print(f"💰 ¡GOLPE AL CASINO! Éxito: {len(data)} juegos extraídos para hoy.")
        
        # 2. EL ACUMULADOR HISTÓRICO (Para la calibración a futuro)
        historical_path = "data_odds/mlb_odds_dataset.json"
        historical_data = {}
        
        # Si el archivo maestro ya existe, lo abrimos y lo cargamos en memoria
        if os.path.exists(historical_path):
            try:
                with open(historical_path, "r", encoding="utf-8") as f:
                    historical_data = json.load(f)
            except Exception as e:
                print(f"⚠️ Error al leer el historial anterior: {e}")
                
        # Inyectamos o actualizamos los momios de hoy en el gran diccionario
        historical_data[today] = data
        
        # Sobrescribimos el archivo maestro con la nueva base de datos expandida
        with open(historical_path, "w", encoding="utf-8") as f:
            json.dump(historical_data, f, indent=4)
            
        print(f"📚 Base de datos histórica actualizada exitosamente con los momios del {today}.")
        
    else:
        print("⚠️ Selenium terminó, pero no encontró momios.")