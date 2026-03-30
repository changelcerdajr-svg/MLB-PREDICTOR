# data_loader.py
# Ingesta V17.0 (Integración Statcast Real vía Baseball Savant + Bayesian Shrinkage Óptimo)

import requests
import datetime
import numpy as np
import pandas as pd
from config import API_URL, USER_AGENT, USE_REAL_TIME, TEST_DATE, STADIUM_COORDS

# Importamos nuestro nuevo motor de extracción
from statcast_scraper import StatcastScraper

# =====================================================================
# CONSTANTES DE ESTABILIZACIÓN STATCAST (Bayesian Shrinkage)
# Decisión Arquitectónica V17.1: Se utiliza Shrinkage basado en Volumen 
# (Método Tom Tango) en lugar de Time-Decay (EMA). Las métricas 'Expected' 
# (xwOBA/xERA) son resistentes a rachas, por lo que el volumen de muestra 
# es mejor predictor del talento real que la recencia cronológica.
# =====================================================================
K_BATTER_XWOBA = 50  # Punto de estabilización de contacto (Aprox 50 PA)
K_PITCHER_XERA = 30  # Punto de estabilización de pitcheo (Aprox 30 IP)
LEAGUE_AVG_XWOBA = 0.315 # Baseline histórico
LEAGUE_AVG_XERA = 4.00   # Baseline histórico
# =====================================================================

class MLBDataLoader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
        self.standings_cache = {} 
        self.player_history_cache = {} 
        self._force_historical_mode = False
        
        # Inicializamos el Scraper de Savant
        self.savant = StatcastScraper()

    def _get(self, endpoint, params=None):
        try:
            url = f"{API_URL}/{endpoint}"
            # AUMENTADO A 15 SEGUNDOS: Las peticiones históricas pesadas tardan más
            r = self.session.get(url, params=params, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e: 
            print(f"\n[!] ERROR DE CONEXIÓN API ({endpoint}): {e}")
            return None

    def get_schedule(self, date_str):
        """Obtiene el calendario de juegos de la API de MLB para una fecha dada."""
        self.current_season_year = int(date_str[:4])
        
        params = {'sportId': 1, 'date': date_str, 'hydrate': 'lineups,probablePitcher,team'}
        data = self._get("schedule", params)
        games_list = []
        
        if not data:
            print(f"  [X] API devolvió vacío para {date_str} (Revisa tu conexión o Timeout)")
            return []
            
        if 'dates' not in data or not data['dates']:
            print(f"  [-] No hay juegos programados por la MLB el {date_str}")
            return []
            
        for date_item in data['dates']:
            for g in date_item['games']:
                try:
                    # Filtramos solo juegos de temporada regular o playoffs
                    if g.get('gameType') not in ['R', 'P', 'F', 'D', 'L', 'W']:
                        continue
                        
                    h_pitcher = g['teams']['home'].get('probablePitcher', {}).get('id')
                    a_pitcher = g['teams']['away'].get('probablePitcher', {}).get('id')
                    
                    if not h_pitcher or not a_pitcher: 
                        # AHORA EL MODELO NOS AVISARÁ SI DESCARTA EL JUEGO POR ESTO
                        # print(f"  -> Omitido: Falta Abridor en {g['teams']['away']['team']['name']} vs {g['teams']['home']['team']['name']}")
                        continue

                    game_info = {
                        'id': g['gamePk'],
                        'date': date_str,
                        'status': g['status']['abstractGameState'],
                        'venue_id': g['venue']['id'],
                        'home_id': g['teams']['home']['team']['id'],
                        'home_name': g['teams']['home']['team']['name'],
                        'home_pitcher': h_pitcher,
                        'away_id': g['teams']['away']['team']['id'],
                        'away_name': g['teams']['away']['team']['name'],
                        'away_pitcher': a_pitcher,
                        'real_winner': None
                    }
                    
                    if game_info['status'] == 'Final':
                        h_score = g['teams']['home'].get('score', 0)
                        a_score = g['teams']['away'].get('score', 0)
                        game_info['real_winner'] = game_info['home_name'] if h_score > a_score else game_info['away_name']

                    games_list.append(game_info)
                except Exception as e:
                    continue
                    
        return games_list

    def get_league_run_environment(self, date_str):
        try:
            data = self._get("standings", {'leagueId': '103,104', 'season': date_str[:4], 'date': date_str, 'hydrate': 'team'})
            total_runs = 0
            total_games = 0
            if data and 'records' in data:
                for division in data['records']:
                    for team in division['teamRecords']:
                        runs = int(team.get('runsScored', 0))
                        wins = int(team.get('wins', 0))
                        losses = int(team.get('losses', 0))
                        total_runs += runs
                        total_games += (wins + losses)
            if total_games > 0:
                league_avg = total_runs / total_games
                if total_games < 200: 
                    weight = total_games / 200
                    league_avg = (league_avg * weight) + (4.30 * (1 - weight))
                return league_avg
        except: pass
        return 4.30 

    def _apply_bayesian_shrinkage(self, current_val, sample_size, k_factor, prior_val):
        if sample_size <= 0: return prior_val
        weight = sample_size / (sample_size + k_factor)
        return (current_val * weight) + (prior_val * (1 - weight))

    def _get_prior_stats(self, pid, stat_group):
        cache_key = f"{pid}_{stat_group}_{self.current_season_year-1}"
        if cache_key in self.player_history_cache:
            return self.player_history_cache[cache_key]
        
        prev_year = self.current_season_year - 1
        
        # 1. Intentamos primero con los datos de Baseball Savant
        if stat_group == 'hitting':
            res = self.savant.get_batter_xwoba(pid, prev_year)
        else:
            res = self.savant.get_pitcher_xera(pid, prev_year)

        # 2. PUNTO 4 AUDITORÍA: Fallback técnico si Savant no tiene datos
        if res is None:
            try:
                # Realizamos la petición a la API de MLB para obtener estadísticas tradicionales
                data = self._get(f"people/{pid}/stats", {'stats': 'season', 'group': stat_group, 'season': prev_year})
                
                if data and 'stats' in data and data['stats'][0].get('splits'):
                    # Definimos 'stat' extrayendo el primer split de la temporada anterior
                    stat = data['stats'][0]['splits'][0]['stat']
                    
                    if stat_group == 'hitting':
                        obp = float(stat.get('onBasePct', 0.320))
                        slg = float(stat.get('slugging', 0.400))
                        
                        # Cálculo raw con pesos de Linear Weights
                        # data_loader.py
                        raw_woba = (1.7 * obp + slg) / 2.65
                        res = raw_woba * 0.885  # Calibración V17.9
                        
            except:
                res = LEAGUE_AVG_XWOBA if stat_group == 'hitting' else LEAGUE_AVG_XERA
        
        # Guardamos en caché y retornamos inmediatamente
        self.player_history_cache[cache_key] = res
        return res
    
    def get_pitcher_xera_stats(self, player_id, year=None):
        import datetime
        if year is None:
            year = getattr(self, 'current_season_year', datetime.date.today().year)
            
        raw_xera = self.savant.get_pitcher_xera(player_id, year)
        if raw_xera is None:
            raw_xera = self.savant.get_pitcher_xera(player_id, year - 1)
            
        # Obtener IP (Innings Pitched) para shrinkage y el K9 real
        ip_data = self._get(f"people/{player_id}/stats", {'stats': 'season', 'group': 'pitching'})
        current_ip = 0.0
        current_k9 = 7.5 # Promedio por defecto
        
        # --- FUNCIÓN DE SEGURIDAD PARA CONVERTIR TEXTO A DECIMAL ---
        def safe_float(val, default):
            try:
                return float(val)
            except (ValueError, TypeError):
                return default
                
        if ip_data and 'stats' in ip_data and ip_data['stats']:
            splits = ip_data['stats'][0].get('splits', [])
            if splits:
                s = splits[0]['stat']
                # Usamos la función de seguridad para evitar el error de '-.--'
                current_ip = safe_float(s.get('inningsPitched', 0.0), 0.0)
                current_k9 = safe_float(s.get('strikeoutsPer9Inn', 7.5), 7.5)
                
        # --- INICIO DE LA CORRECCIÓN CRÍTICA (Prior Bayesiano) ---
        
        # 1. Buscamos el rendimiento histórico real de este pitcher específico
        prior_xera = self._get_prior_stats(player_id, 'pitching')
        
        # 2. Definimos su nivel actual. Si no hay datos de este año, asumimos su histórico.
        base_xera = raw_xera if raw_xera is not None else prior_xera
        
        # 3. Red de seguridad: Solo si es un novato absoluto sin histórico, usamos la media de la liga.
        # Asegúrate de que LEAGUE_AVG_XERA y K_PITCHER_XERA estén definidos al inicio de tu archivo.
        safe_prior = prior_xera if prior_xera is not None else LEAGUE_AVG_XERA
        safe_base = base_xera if base_xera is not None else LEAGUE_AVG_XERA
        
        if current_ip > 0:
            # 4. El Shrinkage ahora "jala" el xERA del año actual hacia el xERA HISTÓRICO del pitcher
            final_xera = ((K_PITCHER_XERA * safe_prior) + (safe_base * current_ip)) / (K_PITCHER_XERA + current_ip)
        else:
            # Si no ha lanzado ni un solo inning este año, su nivel esperado es su histórico
            final_xera = safe_base
            
        # --- FIN DE LA CORRECCIÓN ---
            
        return {'xera': final_xera, 'k9': current_k9}
    
    def get_confirmed_lineup_xwoba(self, game_pk, team_type, vs_hand=None):
        try:
            box = self._get(f"game/{game_pk}/boxscore")
            if not box: return (None, False)
            batters_ids = box['teams'][team_type].get('battingOrder', [])
            if not batters_ids: return (None, False)
            
            ids_str = ",".join([str(x) for x in batters_ids])
            people_data = self._get("people", {'personIds': ids_str, 'hydrate': 'stats(group=[hitting],type=[season])'})
            
            xwoba_map = {}
            if people_data and 'people' in people_data:
                for p in people_data['people']:
                    pid = p['id']
                    current_pa = 0 
                    
                    s = p.get('stats', [])
                    if s and s[0].get('splits'):
                        stat = s[0]['splits'][0]['stat']
                        # CORRECCIÓN AUDITORÍA: Usar PA (Plate Appearances) para estabilización
                        current_pa = int(stat.get('plateAppearances', 0))
                    
                    # 1. Obtener xwOBA específico de split desde el nuevo scraper
                    savant_xwoba = self.savant.get_batter_xwoba(pid, self.current_season_year, vs_hand=vs_hand)
                    
                    # 2. Si es un novato sin split, usamos su xwOBA general como prior
                    if savant_xwoba is None:
                        savant_xwoba = self.savant.get_batter_xwoba(pid, self.current_season_year)
                    
                    # 3. Prior histórico (también intentamos split si existe)
                    prior_xwoba = self._get_prior_stats(pid, 'hitting') # Podrías optimizar esto a split después
                    
                    current_val = savant_xwoba if savant_xwoba is not None else prior_xwoba

                    # 4. Aplicar Shrinkage Bayesiano sobre PA
                    projected_xwoba = self._apply_bayesian_shrinkage(
                        current_val, 
                        current_pa, 
                        K_BATTER_XWOBA, 
                        prior_xwoba
                    )
                    xwoba_map[pid] = projected_xwoba

            weights = [1.32, 1.28, 1.15, 1.05, 1.00, 0.92, 0.85, 0.78, 0.65] 
            weighted_sum = 0
            total_weight = 0
            xwoba_values_list = []
            
            for i, pid in enumerate(batters_ids):
                if i < len(weights):
                    w = weights[i]
                    p_xwoba = xwoba_map.get(pid, LEAGUE_AVG_XWOBA)
                    xwoba_values_list.append(p_xwoba)
                    weighted_sum += (p_xwoba * w)
                    total_weight += w
                    
            if total_weight > 0: 
                # ELIMINADO: cohesion_factor (Punto 7 del Checklist - Ruido estadístico)
                final_xwoba = (weighted_sum / total_weight)
                return (final_xwoba, True)
        except Exception as e: 
            print(f"Error en lineup xwOBA: {e}")
        return (None, False)

    # El resto de las funciones se mantienen sin cambios estructurales
    def get_team_fielding_speed(self, team_id):
        res = {'fielding': 0.985, 'sb_game': 0.5} 
        try:
            f_data = self._get(f"teams/{team_id}/stats", {'stats': 'season', 'group': 'fielding'})
            if f_data and 'stats' in f_data and f_data['stats'] and f_data['stats'][0].get('splits'):
                res['fielding'] = float(f_data['stats'][0]['splits'][0]['stat'].get('fielding', 0.985))
        except: pass
        return res
    
    def get_team_discipline(self, team_id):
        # Proxy para la vulnerabilidad ofensiva frente a arsenales de alto poder (K%)
        try:
            data = self._get(f"teams/{team_id}/stats", {'stats': 'season', 'group': 'hitting'})
            if data and 'stats' in data and data['stats'] and data['stats'][0].get('splits'):
                s = data['stats'][0]['splits'][0]['stat']
                pa = float(s.get('plateAppearances', 1))
                so = float(s.get('strikeouts', 0))
                if pa > 0:
                    return so / pa
        except: pass
        return 0.22 # Promedio histórico de la liga (22% de ponches)
    
    def get_batted_ball_profile(self, entity_id, is_pitcher=False):
        # Devuelve el ratio GO/AO (Ground Outs to Air Outs)
        try:
            group = 'pitching' if is_pitcher else 'hitting'
            endpoint = f"people/{entity_id}/stats" if is_pitcher else f"teams/{entity_id}/stats"
            data = self._get(endpoint, {'stats': 'season', 'group': group})
            if data and 'stats' in data and data['stats'] and data['stats'][0].get('splits'):
                s = data['stats'][0]['splits'][0]['stat']
                go_ao = float(s.get('groundOutsToAirOuts', 1.0))
                return go_ao
        except: 
            pass
        return 1.0 # Promedio neutral de la liga

    def get_bullpen_stats(self, team_id):
        stats = {'era': 4.00, 'whip': 1.30, 'fip': 4.10}
        try:
            data = self._get(f"teams/{team_id}/stats", {'stats': 'season', 'group': 'pitching'})
            if data and 'stats' in data and data['stats'] and data['stats'][0].get('splits'):
                s = data['stats'][0]['splits'][0]['stat']
                ip = float(s.get('inningsPitched', 0.0))
                era = float(s.get('era', 4.00))
                
                # --- NUEVO: Cálculo de FIP (Proxy de xERA) para el Bullpen ---
                if ip > 10:
                    hr = int(s.get('homeRuns', 0))
                    bb = int(s.get('baseOnBalls', 0))
                    k = int(s.get('strikeouts', 0))
                    # Fórmula FIP = ((13*HR) + (3*BB) - (2*K)) / IP + constante (aprox 3.20)
                    fip = ((13 * hr) + (3 * bb) - (2 * k)) / ip + 3.20
                else:
                    fip = era # Fallback si hay muy pocos innings
                # -------------------------------------------------------------

                if ip < 20:
                    w = ip / 30.0 
                    era = (era * w) + (4.00 * (1-w))
                    fip = (fip * w) + (4.10 * (1-w))
                    
                stats['era'] = era
                stats['fip'] = fip
        except: pass
        return stats

    def get_team_stats_split(self, team_id, opponent_hand):
        stats = {'woba': 0.315}
        try:
            split_code = "vsL" if opponent_hand == 'L' else "vsR"
            data = self._get(f"teams/{team_id}/stats", {'stats': 'vsOpponents', 'group': 'hitting', 'sitCodes': split_code})
            if data and 'stats' in data and data['stats'] and data['stats'][0].get('splits'):
                s = data['stats'][0]['splits'][0]['stat']
                
                # CORRECCIÓN AUDITORÍA (Punto 4): Separación de componentes OBP/SLG en splits
                obp = float(s.get('onBasePct', 0.315))
                slg = float(s.get('slugging', 0.410))
                
                # Aplicamos la misma escala técnica para normalizar a wOBA
                stats['woba'] = (1.7 * obp + slg) / 2.65
        except: pass
        return stats
    
    def get_team_pythagorean_data(self, team_id, date_str=None):
        try:
            params = {'leagueId': '103,104', 'season': self.current_season_year}
            if date_str: params['date'] = date_str
            data = self._get("standings", params) 
            if data and 'records' in data:
                for d in data['records']:
                    for r in d['teamRecords']:
                        if r['team']['id'] == team_id: 
                            return r.get('runsScored',0), r.get('runsAllowed',0)
        except: pass
        return 0, 0

    def get_team_momentum(self, team_id, date_str):
        if date_str in self.standings_cache:
            return self.standings_cache[date_str].get(team_id, {'l10': 0.5, 'streak': 0})
        try:
            data = self._get("standings", {'leagueId': '103,104', 'season': date_str[:4], 'date': date_str, 'hydrate': 'team'})
            day_momentum = {}
            if data and 'records' in data:
                for division in data['records']:
                    for team_record in division['teamRecords']:
                        tid = team_record['team']['id']
                        l10_val = 0.5
                        streak_val = 0
                        if 'streak' in team_record:
                            s_code = team_record['streak'].get('streakCode', 'W0')
                            num = int(s_code[1:]) if len(s_code) > 1 else 0
                            streak_val = num if s_code.startswith('W') else -num
                        try:
                           records = team_record.get('records', {})
                           if 'splitRecords' in records:
                               for split in records['splitRecords']:
                                   if split['type'] == 'lastTen':
                                       l10_val = float(split['pct'])
                        except: pass
                        day_momentum[tid] = {'l10': l10_val, 'streak': streak_val}
            self.standings_cache[date_str] = day_momentum
            return day_momentum.get(team_id, {'l10': 0.5, 'streak': 0})
        except: return {'l10': 0.5, 'streak': 0}

    def get_bullpen_fatigue(self, team_id, game_date):
        fatigue_penalty = 0.0
        try:
            import datetime 
            date_obj = datetime.datetime.strptime(game_date, "%Y-%m-%d")
            
            # En inicio de temporada asumimos brazos frescos
            if date_obj.month == 3 or (date_obj.month == 4 and date_obj.day <= 7): 
                return 0.0 
            
            pitcher_workload = {}
            
            # Analizamos la carga de trabajo nominal en las ultimas 72 horas (3 dias)
            for i in range(1, 4): 
                prev_date = (date_obj - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
                data = self._get("schedule", {'sportId': 1, 'date': prev_date, 'teamId': team_id, 'gameType': 'R'})
                
                if data and 'dates' in data and data['dates']:
                    for g in data['dates'][0]['games']:
                        if g['status']['abstractGameState'] == 'Final':
                            game_pk = g['gamePk']
                            
                            box = self._get(f"game/{game_pk}/boxscore")
                            if box:
                                team_side = 'home' if g['teams']['home']['team']['id'] == team_id else 'away'
                                players = box['teams'][team_side]['players']
                                
                                # Extraemos el ID y los pitcheos de cada jugador que vio accion
                                for p_id, p_data in players.items():
                                    stats = p_data.get('stats', {}).get('pitching', {})
                                    pitches = stats.get('numberOfPitches', 0)
                                    
                                    if pitches > 0:
                                        # Filtro para ignorar al abridor (asumimos > 75 pitcheos)
                                        if pitches > 75:
                                            continue
                                            
                                        if p_id not in pitcher_workload:
                                            pitcher_workload[p_id] = {'days_pitched': 0, 'pitches_yesterday': 0}
                                            
                                        pitcher_workload[p_id]['days_pitched'] += 1
                                        if i == 1: # Si fue el juego de ayer
                                            pitcher_workload[p_id]['pitches_yesterday'] = pitches

            # Calculamos exactamente cuantos brazos clave estan inhabilitados hoy
            unavailable_arms = 0
            for p_id, work in pitcher_workload.items():
                # Regla de fatiga 1: Lanzo en dias consecutivos (2 o mas en los ultimos 3 dias)
                if work['days_pitched'] >= 2:
                    unavailable_arms += 1
                # Regla de fatiga 2: Carga extrema ayer (Mas de 25 pitcheos)
                elif work['pitches_yesterday'] >= 25:
                    unavailable_arms += 1
                    
            # Transformamos los brazos inhabilitados en una penalizacion de carreras para el modelo
            if unavailable_arms >= 4:
                fatigue_penalty = 0.45  # Bullpen destruido, usaran novatos/posicion
            elif unavailable_arms == 3:
                fatigue_penalty = 0.30  # Uso severo, cerrador y preparador fuera
            elif unavailable_arms == 2:
                fatigue_penalty = 0.15  # Fatiga moderada alta
            elif unavailable_arms == 1:
                fatigue_penalty = 0.05  # Fatiga normal
                
            return fatigue_penalty
            
        except Exception as e: 
            return 0.10 # Castigo generico conservador en caso de error de conexion

    def get_pitcher_hand(self, pid):
        if not pid: return 'R'
        try:
            d = self._get(f"people/{pid}")
            if d and 'people' in d and len(d['people']) > 0:
                return d['people'][0]['pitchHand']['code']
        except: pass
        return 'R'

    def get_travel_schedule_window(self, target_date_str, days_back=2):
        import datetime
        target_date = datetime.datetime.strptime(target_date_str, "%Y-%m-%d")
        start_date = (target_date - datetime.timedelta(days=days_back)).strftime("%Y-%m-%d")
        data = self._get("schedule", {'sportId': 1, 'startDate': start_date, 'endDate': target_date_str})
        schedule_list = []
        if data and 'dates' in data:
            for date_item in data['dates']:
                d_str = date_item['date']
                for g in date_item['games']:
                    if g.get('gameType') in ['R', 'P', 'F', 'D', 'L', 'W']:
                        schedule_list.append({'date': d_str, 'away_team': g['teams']['away']['team']['id'], 'home_team': g['teams']['home']['team']['id']})
        return pd.DataFrame(schedule_list)

    def get_weather(self, vid):
        # Diccionario de mapeo REAL: MLB Venue ID -> MLB Team ID (para coordenadas)
        # Basado en la estructura oficial de la API de MLB
        venue_to_team = {
            1: 108,    # Angel Stadium (LAA)
            2: 110,    # Oriole Park (BAL)
            3: 139,    # Tropicana Field (TB)
            5: 114,    # Progressive Field (CLE)
            7: 118,    # Kauffman Stadium (KC)
            8: 116,    # Comerica Park (DET) - ID 8 corregido
            9: 111,    # Fenway Park (BOS) - ID 9 corregido
            10: 141,   # Rogers Centre (TOR)
            11: 136,   # T-Mobile Park (SEA) - ID 11 corregido
            12: 145,   # Guaranteed Rate Field (CWS)
            13: 142,   # Target Field (MIN)
            14: 133,   # Oakland Coliseum (OAK)
            15: 109,   # Chase Field (AZ)
            16: 144,   # Truist Park (ATL)
            17: 112,   # Wrigley Field (CHC)
            18: 113,   # Great American Ball Park (CIN)
            19: 115,   # Coors Field (COL)
            20: 158,   # American Family Field (MIL)
            21: 143,   # Citizens Bank Park (PHI)
            22: 119,   # Dodger Stadium (LAD)
            23: 120,   # Nationals Park (WSH)
            24: 137,   # Oracle Park (SF)
            25: 135,   # Petco Park (SD)
            26: 138,   # Busch Stadium (STL)
            27: 140,   # Globe Life Field (TEX)
            29: 146,   # loanDepot park (MIA)
            30: 134,   # PNC Park (PIT)
            31: 121,   # Citi Field (NYM)
            32: 147,   # Yankee Stadium (NYY)
            33: 117,   # Minute Maid Park (HOU)
        }
        
        # Obtenemos el ID del equipo (Team ID) para jalar las coordenadas correctas
        tid = venue_to_team.get(vid, 110)
        c = STADIUM_COORDS.get(tid, {'lat': 40.0, 'lon': -80.0})
        
        try:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                'latitude': c['lat'], 
                'longitude': c['lon'], 
                'current_weather': 'true'
            }
            # Tiempo de espera de 5s para no bloquear el hilo principal
            d = requests.get(url, params=params, timeout=5).json()
            return d['current_weather']
        except: 
            # Fallback neutral si la API de clima falla
            return {'temperature': 20, 'windspeed': 5, 'winddirection': 45}
        
    def get_pitcher_stats(self, pid): return self.get_pitcher_xera_stats(pid)