# statcast_scraper.py
# Motor de Extracción V17.1 (Organización de Directorios)

import pandas as pd
import requests
import io
import os

class StatcastScraper:
    def __init__(self):
        self.base_url = "https://baseballsavant.mlb.com/leaderboard/expected_statistics"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.data_dir = "data_statcast" # Carpeta centralizada
        self.batters_cache = {}
        self.pitchers_cache = {}
        
        # Crear la carpeta si no existe
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def fetch_batters(self, year):
        url = f"{self.base_url}?type=batter&year={year}&position=&team=&min=1&csv=true"
        try:
            r = requests.get(url, headers=self.headers, timeout=10)
            if r.status_code == 200:
                df = pd.read_csv(io.StringIO(r.text))
                file_path = os.path.join(self.data_dir, f"batters_{year}.csv")
                df.to_csv(file_path, index=False)
                self.batters_cache[year] = df.set_index('player_id')['est_woba'].to_dict()
                return True
        except Exception as e:
            print(f"Error descargando batters {year}: {e}")
        return False

    def fetch_pitchers(self, year):
        url = f"{self.base_url}?type=pitcher&year={year}&position=&team=&min=1&csv=true"
        try:
            r = requests.get(url, headers=self.headers, timeout=10)
            if r.status_code == 200:
                df = pd.read_csv(io.StringIO(r.text))
                
                # Buscador dinámico de columna xERA (xera o est_era)
                possible_cols = ['xera', 'est_era', 'expected_era']
                target_col = next((c for c in possible_cols if c in df.columns), None)
                
                if target_col:
                    file_path = os.path.join(self.data_dir, f"pitchers_{year}.csv")
                    df.to_csv(file_path, index=False)
                    self.pitchers_cache[year] = df.set_index('player_id')[target_col].to_dict()
                    return True
        except Exception as e:
            print(f"Error descargando pitchers {year}: {e}")
        return False

    def get_batter_xwoba(self, player_id, year):
        if year not in self.batters_cache:
            file_path = os.path.join(self.data_dir, f"batters_{year}.csv")
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                self.batters_cache[year] = df.set_index('player_id')['est_woba'].to_dict()
            else:
                self.fetch_batters(year)
        return self.batters_cache.get(year, {}).get(player_id)

    def get_pitcher_xera(self, player_id, year):
        if year not in self.pitchers_cache:
            file_path = os.path.join(self.data_dir, f"pitchers_{year}.csv")
            
            if not os.path.exists(file_path):
                self.fetch_pitchers(year)
            
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                possible_cols = ['xera', 'est_era', 'expected_era', 'estimated_era']
                target_col = next((c for c in possible_cols if c in df.columns), None)
                
                if target_col and 'player_id' in df.columns:
                    self.pitchers_cache[year] = df.set_index('player_id')[target_col].to_dict()
                else:
                    self.pitchers_cache[year] = {}
            else:
                self.pitchers_cache[year] = {}

        return self.pitchers_cache.get(year, {}).get(player_id)

if __name__ == "__main__":
    scraper = StatcastScraper()
    print("="*50)
    print("SINCRONIZACIÓN DE DATOS EN CARPETA 'data_statcast'")
    print("="*50)
    
    for y in [2024, 2025, 2026]:
        print(f"🛰️ Procesando temporada {y}...")
        if scraper.fetch_batters(y) and scraper.fetch_pitchers(y):
            print(f"✅ Temporada {y} lista.")