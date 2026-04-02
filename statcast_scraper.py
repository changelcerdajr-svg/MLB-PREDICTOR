# statcast_scraper.py - V17.9 (Resiliencia Industrial y Gestión de Datos)

import os
import io
import time
import json
import requests
import datetime
import pandas as pd

# Variable dinámica para que el caché funcione automáticamente cada año
CURRENT_SEASON = datetime.datetime.now().year

class StatcastScraper:
    def __init__(self):
        self.base_url = "https://baseballsavant.mlb.com/leaderboard/expected_statistics"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (MLB-Predictor-Institutional/17.9)'
        }
        self.data_dir = "data_statcast"
        self.batters_cache = {}
        self.pitchers_cache = {}
        
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def _save_atomic(self, df, file_path):
        """Asegura que el archivo no se corrompa si el proceso se interrumpe."""
        temp_path = file_path + ".tmp"
        df.to_csv(temp_path, index=False)
        os.replace(temp_path, file_path)

    def fetch_batters(self, year, hand=None, force=False):
        """Descarga xwOBA con lógica de ahorro de peticiones y splits reales (V18.0)."""
        file_name = f"batters_{year}_{hand}.csv" if hand else f"batters_{year}.csv"
        file_path = os.path.join(self.data_dir, file_name)

        # No descargar de nuevo si el año ya pasó y el archivo existe
        if not force and year < CURRENT_SEASON and os.path.exists(file_path):
            return True

        # --- CIRUGÍA DE DATOS V18.0: CAMBIO DE ENDPOINT ---
        if hand:
            # Para splits reales, usamos el Player Stat Search
            url = f"https://baseballsavant.mlb.com/player-stat-search/csv?all=true&group=name&player_type=batter&position=&game_type=R&split_type=handedness&year={year}&hand={hand}&current_stat=expected&min_results=1"
        else:
            # Para el talento global base, mantenemos el Leaderboard
            url = f"{self.base_url}?type=batter&year={year}&position=&team=&min=1&csv=true"
        
        try:
            r = requests.get(url, headers=self.headers, timeout=15)
            if r.status_code == 200:
                df = pd.read_csv(io.StringIO(r.text))
                
                # Baseball Savant cambia los nombres de las columnas según el endpoint
                possible_cols = ['xwoba', 'est_woba', 'expected_woba']
                target_col = next((c for c in possible_cols if c in df.columns), None)
                
                # Asegurar que el ID del jugador exista sin importar el formato del CSV
                id_cols = ['player_id', 'id', 'batter']
                id_col = next((c for c in id_cols if c in df.columns), 'player_id')
                
                if target_col and id_col in df.columns:
                    # Limpieza y normalización
                    df[target_col] = df[target_col].fillna(0.315) 
                    df = df.rename(columns={target_col: 'est_woba', id_col: 'player_id'})
                    
                    self._save_atomic(df, file_path)
                    
                    cache_key = f"{year}_{hand}" if hand else year
                    self.batters_cache[cache_key] = df.set_index('player_id')['est_woba'].to_dict()
                    return True
                else:
                    print(f"⚠️ Columnas no encontradas en el CSV de Savant para {year} hand={hand}")
        except Exception as e:
            print(f"⚠️ Error Savant Batters {year}: {e}")
        return False

    def fetch_pitchers(self, year, force=False):
        """Descarga xERA con buscador dinámico de métricas."""
        file_path = os.path.join(self.data_dir, f"pitchers_{year}.csv")
    
        # FIX: Usar la variable dinámica para proteger el caché histórico
        if not force and year < CURRENT_SEASON and os.path.exists(file_path):
            print(f"[CACHE] Datos de pitchers {year} cargados desde disco.")
            return True

        url = f"{self.base_url}?type=pitcher&year={year}&position=&team=&min=1&csv=true"
        try:
            r = requests.get(url, headers=self.headers, timeout=15)
            if r.status_code == 200:
                df = pd.read_csv(io.StringIO(r.text))
                
                possible_cols = ['xera', 'est_era', 'expected_era', 'estimated_era']
                target_col = next((c for c in possible_cols if c in df.columns), None)
                
                if target_col:
                    df[target_col] = df[target_col].fillna(4.00)
                    self._save_atomic(df, file_path)
                    self.pitchers_cache[year] = df.set_index('player_id')[target_col].to_dict()
                    return True
        except Exception as e:
            print(f"⚠️ Error Savant Pitchers {year}: {e}")
        return False

    def get_batter_xwoba(self, player_id, year, vs_hand=None):
        """Recupera xwOBA del caché o disco."""
        cache_key = f"{year}_{vs_hand}" if vs_hand else year
        
        if cache_key not in self.batters_cache:
            file_name = f"batters_{year}_{vs_hand}.csv" if vs_hand else f"batters_{year}.csv"
            file_path = os.path.join(self.data_dir, file_name)
            
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                self.batters_cache[cache_key] = df.set_index('player_id')['est_woba'].to_dict()
            else:
                self.fetch_batters(year, hand=vs_hand)
        
        return self.batters_cache.get(cache_key, {}).get(player_id)

    def get_pitcher_xera(self, player_id, year):
        """Recupera xERA con fallback de seguridad."""
        if year not in self.pitchers_cache:
            file_path = os.path.join(self.data_dir, f"pitchers_{year}.csv")
            if not os.path.exists(file_path):
                self.fetch_pitchers(year)
            
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                possible_cols = ['xera', 'est_era', 'expected_era', 'estimated_era']
                target_col = next((c for c in possible_cols if c in df.columns), None)
                if target_col:
                    self.pitchers_cache[year] = df.set_index('player_id')[target_col].to_dict()

        return self.pitchers_cache.get(year, {}).get(player_id)

if __name__ == "__main__":
    print("🔄 Iniciando descarga de métricas Statcast (xwOBA / xERA)...")
    scraper = StatcastScraper()
    # Sincronización inicial rápida
    for y in [2025, 2026]:
        print(f"   -> Procesando año {y}...")
        scraper.fetch_batters(y)
        scraper.fetch_pitchers(y)
        # Pausa de cortesía para evitar rate-limiting
        time.sleep(2)
    print("✅ ¡Actualización de Statcast completada con éxito!")