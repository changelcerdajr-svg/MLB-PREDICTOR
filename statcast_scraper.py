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
        """Descarga xwOBA con lógica de ahorro de peticiones y splits reales (V18.1)."""
        file_name = f"batters_{year}_{hand}.csv" if hand else f"batters_{year}.csv"
        file_path = os.path.join(self.data_dir, file_name)

        if not force and year < CURRENT_SEASON and os.path.exists(file_path):
            return True

        # --- AÑADE ESTO PARA ROMPER EL SILENCIO ---
        tipo = f"vs {hand}" if hand else "Consolidado"
        print(f"  [📥] Descarga de Emergencia: Bateadores {year} ({tipo})...")

        # --- CIRUGÍA DE DATOS V18.1: URL CORREGIDA ---
        if hand:
            # Usar el endpoint líder robusto, pero añadiendo la mano del pitcher
            url = f"{self.base_url}?type=batter&year={year}&position=&team=&min=1&pitch_hand={hand}&csv=true"
        else:
            url = f"{self.base_url}?type=batter&year={year}&position=&team=&min=1&csv=true"
        
        try:
            r = requests.get(url, headers=self.headers, timeout=15)
            if r.status_code == 200:
                df = pd.read_csv(io.StringIO(r.text))
                
                possible_cols = ['xwoba', 'est_woba', 'expected_woba']
                target_col = next((c for c in possible_cols if c in df.columns), None)
                
                id_cols = ['player_id', 'id', 'batter']
                id_col = next((c for c in id_cols if c in df.columns), 'player_id')
                
                if target_col and id_col in df.columns:
                    df[target_col] = df[target_col].fillna(0.315) 
                    df = df.rename(columns={target_col: 'est_woba', id_col: 'player_id'})
                    
                    self._save_atomic(df, file_path)
                    
                    cache_key = f"{year}_{hand}" if hand else year
                    self.batters_cache[cache_key] = df.set_index('player_id')['est_woba'].to_dict()
                    return True
                else:
                    print(f"  [!] Alerta: Columnas no encontradas en el CSV para {year} (hand={hand})")
            else:
                # AHORA SÍ NOS AVISARÁ SI LA API NOS RECHAZA
                print(f"  [❌] Error API: Savant respondió con código {r.status_code} para {year} (hand={hand})")
                
        except Exception as e:
            print(f"  [⚠️] Excepción en Savant Batters {year}: {e}")
        return False

    def fetch_pitchers(self, year, force=False):
        """Descarga xERA con buscador dinámico de métricas."""
        file_path = os.path.join(self.data_dir, f"pitchers_{year}.csv")
    
        if not force and year < CURRENT_SEASON and os.path.exists(file_path):
            return True

        # --- AÑADE ESTO PARA ROMPER EL SILENCIO ---
        print(f"  [📥] Descarga de Emergencia: Pitchers {year}...")

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
        """Recupera xwOBA con sistema de respaldo para evitar bloqueos por falta de splits L/R."""
        cache_key = f"{year}_{vs_hand}" if vs_hand else str(year)
        
        if cache_key not in self.batters_cache:
            file_name = f"batters_{year}_{vs_hand}.csv" if vs_hand else f"batters_{year}.csv"
            file_path = os.path.join(self.data_dir, file_name)
            
            # 1. Si no existe el específico, intentamos descargarlo
            if not os.path.exists(file_path):
                self.fetch_batters(year, hand=vs_hand)
            
            # 2. SISTEMA DE RESPALDO (El Fix):
            # Si buscaba un archivo 'R' o 'L' y no se creó, usamos el general.
            if not os.path.exists(file_path) and vs_hand:
                general_path = os.path.join(self.data_dir, f"batters_{year}.csv")
                if os.path.exists(general_path):
                    # Encontramos el archivo general que sí tienes en tu carpeta
                    file_path = general_path 
            
            # 3. Leemos el archivo que hayamos encontrado
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                df['player_id'] = pd.to_numeric(df['player_id'], errors='coerce')
                self.batters_cache[cache_key] = df.set_index('player_id')['est_woba'].to_dict()
            else:
                # Vacuna contra ciclos infinitos si de plano no hay datos
                self.batters_cache[cache_key] = {} 
                
        try:
            player_id_num = int(player_id)
        except (ValueError, TypeError):
            return None
            
        return self.batters_cache[cache_key].get(player_id_num)
    
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
    print("🔄 Iniciando descarga de métricas Statcast (xwOBA / xERA) V18.0...")
    scraper = StatcastScraper()
    
    # Sincronización completa (Años relevantes para backtest y temporada actual)
    # Incluimos desde 2023 para asegurarnos que los Priors históricos funcionen
    for y in [2023, 2024, 2025, 2026]:
        print(f"\n🚀 Procesando año {y}...")
        
        # 1. Talento Consolidado
        print("   -> Descargando Talento Consolidado (Bateadores/Pitchers)...")
        scraper.fetch_batters(y, force=True) 
        scraper.fetch_pitchers(y, force=True)
        time.sleep(2) # Cortesía API
        
        # 2. Platoon Splits (El secreto para el Alpha real)
        print("   -> Descargando Platoon Splits (vs Zurdos y Zurdos)...")
        scraper.fetch_batters(y, hand='R', force=True) # Bateadores vs Derechos
        time.sleep(2)
        scraper.fetch_batters(y, hand='L', force=True) # Bateadores vs Zurdos
        time.sleep(2)
        
    print("\n✅ ¡Actualización de Statcast completada con éxito! (Platoon Splits activos)")