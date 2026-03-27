# statcast_scraper.py
# Módulo de Extracción de Baseball Savant (Expected Statistics)

import pandas as pd
import requests
import io

class StatcastScraper:
    def __init__(self):
        # Disfrazamos a nuestro bot como un navegador web normal
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        self.batters_cache = None
        self.pitchers_cache = None
        self.current_year = None

    def _fetch_savant_data(self, player_type, year):
        """
        Descarga el CSV oculto de Baseball Savant y lo convierte en un DataFrame.
        player_type: 'batter' o 'pitcher'
        """
        print(f"🛰️ Descargando radares de {player_type}s ({year}) desde Baseball Savant...")
        url = f"https://baseballsavant.mlb.com/leaderboard/expected_statistics?type={player_type}&year={year}&position=&team=&min=1&csv=true"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            # Leemos el texto del CSV directamente a la memoria de Pandas
            df = pd.read_csv(io.StringIO(response.text))
            
            # Limpiamos el DataFrame para que el ID sea el índice principal
            df.set_index('player_id', inplace=True)
            return df
            
        except Exception as e:
            print(f"❌ Error al conectar con Savant: {e}")
            return None

    def load_season_data(self, year):
        """Carga ambas tablas en memoria para consultas ultra-rápidas."""
        if self.current_year != year or self.batters_cache is None:
            self.batters_cache = self._fetch_savant_data('batter', year)
            self.pitchers_cache = self._fetch_savant_data('pitcher', year)
            self.current_year = year

    def get_batter_xwoba(self, player_id, year):
        """Devuelve el xwOBA real basado en la física del batazo."""
        self.load_season_data(year)
        if self.batters_cache is not None and player_id in self.batters_cache.index:
            try:
                # Extraemos la columna 'est_woba' (Expected wOBA)
                return float(self.batters_cache.loc[player_id, 'est_woba'])
            except: pass
        return None # Retorna None si el jugador no existe ese año

    def get_pitcher_xera(self, player_id, year):
        """Devuelve el xERA real basado en la calidad del contacto permitido."""
        self.load_season_data(year)
        if self.pitchers_cache is not None and player_id in self.pitchers_cache.index:
            try:
                # Extraemos 'est_ba' (xBA), 'est_slg' (xSLG), o xwOBA para derivar xERA.
                # Savant no entrega xERA directo en este CSV, pero xwOBA es perfectamente equivalente para pitchers.
                # Lo convertimos a una escala de ERA (Aprox: xwOBA * 13 - 0.5)
                pitcher_xwoba = float(self.pitchers_cache.loc[player_id, 'est_woba'])
                xera_approx = (pitcher_xwoba * 12.5) - 0.2
                return round(xera_approx, 2)
            except: pass
        return None

# --- ZONA DE PRUEBAS ---
if __name__ == "__main__":
    print("="*50)
    print(" PRUEBA DE MOTOR STATCAST (BASEBALL SAVANT)")
    print("="*50)
    
    scraper = StatcastScraper()
    
    # Pruebas con datos de 2024
    YEAR = 2024
    
    # ID de Aaron Judge (Bateador Élite)
    judge_id = 592450
    judge_xwoba = scraper.get_batter_xwoba(judge_id, YEAR)
    print(f"⚾ Aaron Judge (ID: {judge_id}) -> xwOBA {YEAR}: {judge_xwoba}")
    
    # ID de Tarik Skubal (Pitcher Élite)
    skubal_id = 669373
    skubal_xera = scraper.get_pitcher_xera(skubal_id, YEAR)
    print(f"⚾ Tarik Skubal (ID: {skubal_id}) -> xERA {YEAR}: {skubal_xera}")
    
    print("="*50)