import time
import json
import os
from bs4 import BeautifulSoup
import undetected_chromedriver as uc  # <--- NUEVO IMPORT
from selenium.webdriver.chrome.options import Options

# --- CONFIGURACIÓN ---
FECHAS_FALTANTES = ["2026-03-25", "2026-04-03"] # Agrega aquí los días que te faltan
ARCHIVO_JSON = 'data_odds/mlb_odds_dataset.json'

def cargar_dataset():
    if os.path.exists(ARCHIVO_JSON):
        with open(ARCHIVO_JSON, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def guardar_dataset(data):
    with open(ARCHIVO_JSON, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"✅ Dataset actualizado y guardado en {ARCHIVO_JSON}")

def iniciar_navegador():
    print("Iniciando navegador indetectable...")
    options = uc.ChromeOptions()
    
    # IMPORTANTE: Para la primera prueba no usaremos "headless" (invisible).
    # Queremos que la ventana se abra para ver con nuestros propios ojos si nos deja pasar.
    # Una vez que confirmemos que funciona, puedes agregar options.headless = True
    
    driver = uc.Chrome(options=options, version_main=146)
    return driver

def scrapear_covers_dia(driver, fecha):
    print(f"Consultando Covers.com para la fecha: {fecha}...")
    url = f"https://www.covers.com/sports/mlb/matchups?selectedDate={fecha}"
    driver.get(url)
    
    # Le damos un poco más de tiempo por si la página está pesada
    time.sleep(8) 
    
    # --- MODO DEPURACIÓN (LA CÁMARA) ---
    try:
        driver.save_screenshot(f"debug_{fecha}.png")
        with open(f"debug_{fecha}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"  [i] Captura de pantalla guardada: debug_{fecha}.png")
    except Exception as e:
        print(f"  [!] No se pudo guardar la captura: {e}")
    # -----------------------------------
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    juegos = soup.find_all('div', class_='cmg_matchup_game_box')
    
    dia_data = []
    
    for juego in juegos:
        try:
            # Extraer nombres de los equipos
            away_team = juego['data-away-team-fullname-search']
            home_team = juego['data-home-team-fullname-search']
            
            # Extraer momios del Moneyline (Consenso de Las Vegas)
            # Covers suele guardar el momio de cierre en elementos con clase 'cmg_matchup_list_odds_ml'
            odds_elements = juego.find_all('div', class_='cmg_matchup_list_odds_ml')
            
            if len(odds_elements) >= 2:
                away_odds_str = odds_elements[0].text.strip()
                home_odds_str = odds_elements[1].text.strip()
                
                # Limpiar el string para convertirlo a entero (ej. "+150" -> 150)
                away_odds = int(away_odds_str.replace('+', '').replace('pk', '100')) if away_odds_str else None
                home_odds = int(home_odds_str.replace('+', '').replace('pk', '100')) if home_odds_str else None
                
                if away_odds and home_odds:
                    # Formatear EXACTAMENTE como lo espera tu get_real_odds en backtest_master.py
                    game_entry = {
                        "gameView": {
                            "homeTeam": {"fullName": home_team},
                            "awayTeam": {"fullName": away_team}
                        },
                        "odds": {
                            "moneyline": [
                                {
                                    # Usamos vegas_consensus para que tu script lo lea correctamente
                                    "sportsbook": "vegas_consensus", 
                                    "currentLine": {
                                        "homeOdds": home_odds,
                                        "awayOdds": away_odds
                                    }
                                }
                            ]
                        }
                    }
                    dia_data.append(game_entry)
                    print(f"  -> Recuperado: {away_team} ({away_odds}) @ {home_team} ({home_odds})")
        except Exception as e:
            continue # Si un juego está en blanco o pospuesto, lo saltamos
            
    return dia_data

def ejecutar_rescate():
    dataset = cargar_dataset()
    driver = iniciar_navegador()
    
    nuevos_datos = 0
    
    try:
        for fecha in FECHAS_FALTANTES:
            # Si la fecha ya existe y tiene datos, la saltamos para no duplicar
            if fecha in dataset and len(dataset[fecha]) > 0:
                print(f"La fecha {fecha} ya existe en el dataset. Saltando...")
                continue
                
            datos_dia = scrapear_covers_dia(driver, fecha)
            
            if datos_dia:
                dataset[fecha] = datos_dia
                nuevos_datos += 1
            else:
                print(f"  [!] No se encontraron momios para {fecha}.")
                
    finally:
        driver.quit()
        
    if nuevos_datos > 0:
        guardar_dataset(dataset)
    else:
        print("No hubo cambios en el dataset.")

if __name__ == "__main__":
    ejecutar_rescate()