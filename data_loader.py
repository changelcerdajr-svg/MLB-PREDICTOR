# data_loader.py
# Ingesta V17.0 (Integración Statcast Real vía Baseball Savant + Bayesian Shrinkage Óptimo)

import requests
import datetime
import numpy as np
import pandas as pd
from config import API_URL, USER_AGENT, USE_REAL_TIME, TEST_DATE, STADIUM_COORDS
from config import RAW_WOBA_REGRESSOR, LINEUP_PA_VOLUME_MULTIPLIERS

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
        
        # Declaramos los cachés aquí para que existan en todo el archivo
        self.boxscore_cache = {} 
        self.schedule_cache = {} 
        # Carga en memoria de la Capa 2 (Hot Hand)
        self.hot_hand_data = {}
        try:
            import json
            with open('data_odds/hot_hand.json', 'r') as f:
                self.hot_hand_data = json.load(f)
        except Exception as e:
            pass # Si el archivo no existe o falla, el modelo opera normalmente con la Capa 1

        self._force_historical_mode = False
        
        # Inicializamos el Scraper de Savant
        self.savant = StatcastScraper()

    def reload_hot_hand(self):
            """Actualiza el caché en memoria para la simulación de ventana móvil."""
            import json
            try:
                with open('data_odds/hot_hand.json', 'r') as f:
                    self.hot_hand_data = json.load(f)
            except Exception:
                self.hot_hand_data = {}

    def _get(self, endpoint, params=None, timeout=15):
        import time 
        url = f"{API_URL}/{endpoint}"
        max_retries = 3
        retries = 0
        
        while retries < max_retries:
            try:
                r = self.session.get(url, params=params, timeout=timeout)
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                return r.json()
            except requests.exceptions.ConnectionError:
                print(f"\n[!] ⚠️ SIN INTERNET. Reintentando en 10s... ({endpoint})")
                time.sleep(10)
                retries += 1
            except requests.exceptions.Timeout:
                print(f"\n[!] ⚠️ TIMEOUT DE MLB. Reintentando en 10s... ({endpoint})")
                time.sleep(10)
                retries += 1
            except Exception as e: 
                print(f"\n[!] ERROR API ({endpoint}): {e}")
                return None
                
        print(f"\n[X] Límite de 3 reintentos agotado para {endpoint}. Abortando.")
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
                        
                        # MINOR FIX: Prevención de contaminación por empates
                        if h_score > a_score:
                            game_info['real_winner'] = game_info['home_name']
                        elif a_score > h_score:
                            game_info['real_winner'] = game_info['away_name']
                        else:
                            game_info['real_winner'] = None # Juego empatado/suspendido

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
                        
                        total_runs += runs
                        
                        # FIX BUG #3: Solo sumamos 'wins' para no contar doble los partidos
                        total_games += wins
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
                        # --- INICIO CORRECCIÓN A4: Cálculo wOBA real ---
                        pa = float(stat.get('plateAppearances', 0))
                        
                        if pa > 0:
                            bb = float(stat.get('baseOnBalls', 0))
                            ibb = float(stat.get('intentionalWalks', 0))
                            hbp = float(stat.get('hitByPitch', 0))
                            hits = float(stat.get('hits', 0))
                            doubles = float(stat.get('doubles', 0))
                            triples = float(stat.get('triples', 0))
                            hr = float(stat.get('homeRuns', 0))
                            
                            ubb = bb - ibb # Bases por bolas no intencionales
                            singles = hits - doubles - triples - hr
                            
                            # Pesos wOBA modernos (Aprox. temporada 2024)
                            woba_num = (0.69 * ubb) + (0.72 * hbp) + (0.88 * singles) + (1.25 * doubles) + (1.59 * triples) + (2.05 * hr)
                            woba_den = pa - ibb
                            
                            raw_woba = woba_num / woba_den if woba_den > 0 else LEAGUE_AVG_XWOBA
                            res = raw_woba * RAW_WOBA_REGRESSOR
                        else:
                            # Fallback extremo si no hay turnos al bate
                            obp = float(stat.get('onBasePct', 0.320))
                            slg = float(stat.get('slugging', 0.400))
                            res = ((1.7 * obp + slg) / 2.65) * RAW_WOBA_REGRESSOR
                        # --- FIN CORRECCIÓN A4 ---
                        
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
        current_bf = 0.0 
        current_babip = 0.300 # <--- NUEVA VARIABLE DE SUERTE
        
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
                current_ip = safe_float(s.get('inningsPitched', 0.0), 0.0)
                current_k9 = safe_float(s.get('strikeoutsPer9Inn', 7.5), 7.5)
                # M2: Extraemos los Bateadores Enfrentados (BF)
                current_bf = safe_float(s.get('battersFaced', current_ip * 4.25), current_ip * 4.25)
                # NUEVO: Extraemos el BABIP (Batting Average on Balls In Play)
                current_babip = safe_float(s.get('babip', 0.300), 0.300)
                
        # --- INICIO DE LA CORRECCIÓN CRÍTICA (Prior Bayesiano) ---
        prior_xera = self._get_prior_stats(player_id, 'pitching')
        base_xera = raw_xera if raw_xera is not None else prior_xera
        
        safe_prior = prior_xera if prior_xera is not None else LEAGUE_AVG_XERA
        safe_base = base_xera if base_xera is not None else LEAGUE_AVG_XERA
        
        # M2: Usamos BF en lugar de IP. 125 BF equivale a aprox 30 IP (Punto de estabilización)
        K_BF = 125.0 
        
        if current_bf > 0:
            final_xera = ((K_BF * safe_prior) + (safe_base * current_bf)) / (K_BF + current_bf)
        else:
            final_xera = safe_base
            
        # Retornamos IP para el simulador
        return {'xera': final_xera, 'k9': current_k9, 'ip': current_ip, 'babip': current_babip}

    def _blend_hot_hand(self, base_xwoba, player_id, hot_hand_cache, weight=0.20):
        recent = hot_hand_cache.get(str(player_id)) or hot_hand_cache.get(int(player_id))
        if recent is None:
            return base_xwoba  
            
        # Normalización matemática: escalamos el xwOBAcon al entorno del xwOBA general
        normalized_recent = recent * (LEAGUE_AVG_XWOBA / 0.380)
        
        # Al estar normalizado, podemos usar un peso ligeramente más agresivo (20%)
        return (base_xwoba * (1.0 - weight)) + (normalized_recent * weight)
    
    def get_confirmed_lineup_xwoba(self, game_pk, team_type, vs_hand=None, team_id=None, use_hot_hand=True):
        try:
            # 1. Buscamos el lineup en el endpoint de schedule (disponible pre-juego)
            url = f"schedule?gamePk={game_pk}&hydrate=lineups"
            data = self._get(url)
            
            if not data or 'dates' not in data or not data['dates']:
                return (None, False)
                
            game_data = data['dates'][0]['games'][0]
            lineups = game_data.get('lineups', {})
            
            # 2. Separamos la búsqueda dependiendo de si somos local o visitante
            if team_type == 'home':
                players = lineups.get('homePlayers', [])
            else:
                players = lineups.get('awayPlayers', [])
                
            # 3. Extraemos la lista limpia de los IDs de los 9 bateadores
            batters_ids = [player['id'] for player in players]
            
            # Si la MLB aún no publica el lineup, abortamos suavemente
            if not batters_ids or len(batters_ids) < 9:
                return (None, False)

            # --- LÓGICA MATEMÁTICA ORIGINAL ---
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
                        current_pa = int(stat.get('plateAppearances', 0))
                    
                    savant_xwoba = self.savant.get_batter_xwoba(pid, self.current_season_year, vs_hand=vs_hand)

                    # Si no hay muestra suficiente en el split, usamos el global como respaldo (Shrinkage)
                    if savant_xwoba is None:
                        savant_xwoba = self.savant.get_batter_xwoba(pid, self.current_season_year)
                    
                    # Si es novato o tiene pocos turnos vs esa mano, usamos el global como respaldo
                    if savant_xwoba is None:
                        savant_xwoba = self.savant.get_batter_xwoba(pid, self.current_season_year)
                    
                    # Prior histórico
                    prior_xwoba = self._get_prior_stats(pid, 'hitting')
                    
                    current_val = savant_xwoba if savant_xwoba is not None else prior_xwoba

                    # Seguro contra novatos absolutos sin historial
                    if current_val is None:
                        current_val = LEAGUE_AVG_XWOBA
                    if prior_xwoba is None:
                        prior_xwoba = LEAGUE_AVG_XWOBA

                    # Aplicar Shrinkage Bayesiano sobre PA (CAPA 1: Talento Base)
                    projected_xwoba = self._apply_bayesian_shrinkage(
                        current_val, current_pa, K_BATTER_XWOBA, prior_xwoba
                    )
                    
                    # --- INICIO INTEGRACIÓN CAPA 2 (HOT HAND) ---
                    # Llamamos a la función modular usando el caché en memoria y la calibración del 18%
                    if use_hot_hand:
                        projected_xwoba = self._blend_hot_hand(projected_xwoba, pid, self.hot_hand_data)
                    
                    xwoba_map[pid] = projected_xwoba

            weights = LINEUP_PA_VOLUME_MULTIPLIERS
            weighted_sum = 0
            total_weight = 0
            
            for i, pid in enumerate(batters_ids):
                if i < len(weights):
                    w = weights[i]
                    p_xwoba = xwoba_map.get(pid, LEAGUE_AVG_XWOBA)
                    weighted_sum += (p_xwoba * w)
                    total_weight += w
                    
            if total_weight > 0: 
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
        if len(self.boxscore_cache) > 500:
            self.boxscore_cache.clear()
        if len(self.schedule_cache) > 500:
            self.schedule_cache.clear()

        fatigue_penalty = 0.0
        try:
            import datetime 
            date_obj = datetime.datetime.strptime(game_date, "%Y-%m-%d")
            
            if date_obj.month == 3 or (date_obj.month == 4 and date_obj.day <= 7): 
                return 0.0 
            
            pitcher_workload = {}
            
            for i in range(1, 4): 
                prev_date = (date_obj - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
                
                sched_key = f"{prev_date}_{team_id}"
                if sched_key not in self.schedule_cache:
                    self.schedule_cache[sched_key] = self._get("schedule", {'sportId': 1, 'date': prev_date, 'teamId': team_id, 'gameType': 'R'})
                
                data = self.schedule_cache[sched_key]
                
                if data and 'dates' in data and data['dates']:
                    for g in data['dates'][0]['games']:
                        if g['status']['abstractGameState'] == 'Final':
                            game_pk = g['gamePk']
                            
                            if game_pk not in self.boxscore_cache:
                                self.boxscore_cache[game_pk] = self._get(f"game/{game_pk}/boxscore")
                            
                            box = self.boxscore_cache[game_pk]
                            
                            if box:
                                team_side = 'home' if g['teams']['home']['team']['id'] == team_id else 'away'
                                players = box['teams'][team_side]['players']
                                
                                for p_id, p_data in players.items():
                                    stats = p_data.get('stats', {}).get('pitching', {})
                                    pitches = stats.get('numberOfPitches', 0)
                                    
                                    if pitches > 0:
                                        if pitches > 75:
                                            continue
                                            
                                        if p_id not in pitcher_workload:
                                            pitcher_workload[p_id] = {'days_pitched': 0, 'pitches_yesterday': 0}
                                            
                                        pitcher_workload[p_id]['days_pitched'] += 1
                                        if i == 1: 
                                            pitcher_workload[p_id]['pitches_yesterday'] = pitches

            unavailable_arms = 0
            for p_id, work in pitcher_workload.items():
                if work['days_pitched'] >= 2:
                    unavailable_arms += 1
                elif work['pitches_yesterday'] >= 25:
                    unavailable_arms += 1
                    
            if unavailable_arms >= 4:
                fatigue_penalty = 0.45 
            elif unavailable_arms == 3:
                fatigue_penalty = 0.30 
            elif unavailable_arms == 2:
                fatigue_penalty = 0.15 
            elif unavailable_arms == 1:
                fatigue_penalty = 0.05 
                
            return fatigue_penalty
            
        except Exception as e: 
            return 0.10

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