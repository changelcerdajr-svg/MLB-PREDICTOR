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
            r = self.session.get(url, params=params, timeout=6)
            r.raise_for_status()
            return r.json()
        except: return None

    def get_schedule(self, date_str):
        """Obtiene el calendario de juegos de la API de MLB para una fecha dada."""
        self.current_season_year = int(date_str[:4]) # Línea restaurada
        
        params = {'sportId': 1, 'date': date_str, 'hydrate': 'lineups,probablePitcher,team'}
        data = self._get("schedule", params)
        games_list = []
        
        if not data or 'dates' not in data or not data['dates']:
            return []
            
        for date_item in data['dates']:
            for g in date_item['games']:
                try:
                    # Filtramos solo juegos de temporada regular o playoffs
                    if g.get('gameType') not in ['R', 'P', 'F', 'D', 'L', 'W']:
                        continue
                        
                    h_pitcher = g['teams']['home'].get('probablePitcher', {}).get('id')
                    a_pitcher = g['teams']['away'].get('probablePitcher', {}).get('id')
                    
                    if not h_pitcher or not a_pitcher: continue

                    game_info = {
                        'id': g['gamePk'],
                        'date': date_str,
                        'status': g['status']['abstractGameState'],
                        'venue_id': g['venue']['id'],
                        'home_id': g['teams']['home']['team']['id'],
                        'home_name': g['teams']['home']['team']['name'],  # <-- CORREGIDO AQUÍ
                        'home_pitcher': h_pitcher,
                        'away_id': g['teams']['away']['team']['id'],
                        'away_name': g['teams']['away']['team']['name'],  # <-- CORREGIDO AQUÍ
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
        
        # Primero intentamos sacar el dato histórico desde Baseball Savant
        if stat_group == 'hitting':
            res = self.savant.get_batter_xwoba(pid, prev_year)
            if res is not None:
                self.player_history_cache[cache_key] = res
                return res
        else:
            res = self.savant.get_pitcher_xera(pid, prev_year)
            if res is not None:
                self.player_history_cache[cache_key] = res
                return res

        # Fallback a OPS/FIP histórico si falla Savant
        try:
            data = self._get(f"people/{pid}/stats", {'stats': 'season', 'group': stat_group, 'season': prev_year})
            if data and 'stats' in data and data['stats'] and data['stats'][0].get('splits'):
                stat = data['stats'][0]['splits'][0]['stat']
                if stat_group == 'hitting':
                    ops = float(stat.get('ops', 0.720))
                    res = ops * (0.315 / 0.720) # Conversión aproximada para el año anterior
                else:
                    ip = float(stat.get('inningsPitched', 1.0))
                    if ip > 10:
                        hr = int(stat.get('homeRuns', 0))
                        bb = int(stat.get('baseOnBalls', 0))
                        k = int(stat.get('strikeouts', 0))
                        res = ((13 * hr) + (3 * bb) - (2 * k)) / ip + 3.20
                    else:
                        res = float(stat.get('era', LEAGUE_AVG_XERA))
                self.player_history_cache[cache_key] = res
                return res
        except: pass
        
        default = LEAGUE_AVG_XWOBA if stat_group == 'hitting' else LEAGUE_AVG_XERA
        self.player_history_cache[cache_key] = default
        return default

    def get_pitcher_xera_stats(self, player_id, year=None):
        if year is None:
            year = getattr(self, 'current_season_year', datetime.date.today().year)
            
        raw_xera = self.savant.get_pitcher_xera(player_id, year)
        if raw_xera is None:
            raw_xera = self.savant.get_pitcher_xera(player_id, year - 1)
            
        # Obtener IP (Innings Pitched) para shrinkage y el K9 real
        ip_data = self._get(f"people/{player_id}/stats", {'stats': 'season', 'group': 'pitching'})
        current_ip = 0.0
        current_k9 = 7.5 # Promedio por defecto
        
        if ip_data and 'stats' in ip_data and ip_data['stats']:
            splits = ip_data['stats'][0].get('splits', [])
            if splits:
                s = splits[0]['stat']
                current_ip = float(s.get('inningsPitched', 0.0))
                current_k9 = float(s.get('strikeoutsPer9Inn', 7.5))
                
        # Aplicamos el Shrinkage usando los innings reales
        base_xera = raw_xera if raw_xera is not None else LEAGUE_AVG_XERA
        
        if current_ip > 0:
            final_xera = (K_PITCHER_XERA * LEAGUE_AVG_XERA + base_xera * current_ip) / (K_PITCHER_XERA + current_ip)
        else:
            final_xera = base_xera
            
        return {'xera': final_xera, 'k9': current_k9}

    def get_confirmed_lineup_xwoba(self, game_pk, team_type):
        try:
            box = self._get(f"game/{game_pk}/boxscore")
            if not box: return (None, False)
            batters_ids = box['teams'][team_type].get('battingOrder', [])
            if not batters_ids: return (None, False)
            
            ids_str = ",".join([str(x) for x in batters_ids])
            # MLB API solo para volumen (At Bats)
            people_data = self._get("people", {'personIds': ids_str, 'hydrate': 'stats(group=[hitting],type=[season])'})
            
            xwoba_map = {}
            if people_data and 'people' in people_data:
                for p in people_data['people']:
                    pid = p['id']
                    current_ab = 0
                    
                    s = p.get('stats', [])
                    if s and s[0].get('splits'):
                        stat = s[0]['splits'][0]['stat']
                        current_ab = int(stat.get('atBats', 0))
                    
                    # Extraemos el xwOBA real desde Savant
                    savant_xwoba = self.savant.get_batter_xwoba(pid, self.current_season_year)
                    
                    if savant_xwoba is not None:
                        current_xwoba = savant_xwoba
                    else:
                        # Fallback a OPS convertido si Savant no tiene el dato
                        try:
                            ops = float(s[0]['splits'][0]['stat'].get('ops', 0.720))
                            current_xwoba = ops * (0.315 / 0.720)
                        except:
                            current_xwoba = LEAGUE_AVG_XWOBA

                    prior_xwoba = self._get_prior_stats(pid, 'hitting')
                    projected_xwoba = self._apply_bayesian_shrinkage(current_xwoba, current_ab, K_BATTER_XWOBA, prior_xwoba)
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
                lineup_variance = np.std(xwoba_values_list) if len(xwoba_values_list) > 0 else 0
                cohesion_factor = 1.0 + (0.05 * (0.04 - lineup_variance))
                final_xwoba = (weighted_sum / total_weight) * cohesion_factor
                return (final_xwoba, True)
        except Exception as e: 
            pass
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

    def get_bullpen_stats(self, team_id):
        stats = {'era': 4.00, 'whip': 1.30}
        try:
            data = self._get(f"teams/{team_id}/stats", {'stats': 'season', 'group': 'pitching'})
            if data and 'stats' in data and data['stats'] and data['stats'][0].get('splits'):
                s = data['stats'][0]['splits'][0]['stat']
                ip = float(s.get('inningsPitched', 0.0))
                era = float(s.get('era', 4.00))
                if ip < 20:
                    w = ip / 30.0 
                    era = (era * w) + (4.00 * (1-w))
                stats['era'] = era
        except: pass
        return stats

    def get_team_stats_split(self, team_id, opponent_hand):
        stats = {'woba': 0.315}
        try:
            split_code = "vsL" if opponent_hand == 'L' else "vsR"
            data = self._get(f"teams/{team_id}/stats", {'stats': 'vsOpponents', 'group': 'hitting', 'sitCodes': split_code})
            if data and 'stats' in data and data['stats'] and data['stats'][0].get('splits'):
                s = data['stats'][0]['splits'][0]['stat']
                # Transformamos el OPS del split a la escala wOBA (ya que Savant no da splits tan fácil)
                ops = float(s.get('ops', 0.720))
                stats['woba'] = ops * (0.315 / 0.720)
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
        fatigue_score = 0.0
        try:
            import datetime 
            date_obj = datetime.datetime.strptime(game_date, "%Y-%m-%d")
            if date_obj.month == 3 or (date_obj.month == 4 and date_obj.day <= 7): return 0.0 
            for i in range(1, 4): 
                prev_date = (date_obj - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
                data = self._get("schedule", {'sportId': 1, 'date': prev_date, 'teamId': team_id, 'gameType': 'R'})
                if data and 'dates' in data and data['dates']:
                    for g in data['dates'][0]['games']:
                        if g['status']['abstractGameState'] == 'Final':
                            is_home = g['teams']['home']['team']['id'] == team_id
                            runs_allowed = g['teams']['home']['score'] if not is_home else g['teams']['away']['score']
                            if runs_allowed > 5: fatigue_score += 0.12
                            fatigue_score += 0.08 
            return min(0.4, fatigue_score) 
        except Exception as e: return 0.1

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
        import pandas as pd
        return pd.DataFrame(schedule_list)
    
    def get_weather(self, vid):
        c = STADIUM_COORDS.get(vid, {'lat': 40, 'lon': -80})
        try:
            d = requests.get("https://api.open-meteo.com/v1/forecast", params={'latitude':c['lat'], 'longitude':c['lon'], 'current_weather':'true'}, timeout=3).json()
            return d['current_weather']
        except: return {'temperature': 20, 'windspeed': 5, 'winddirection': 45}

    def get_pitcher_stats(self, pid): return self.get_pitcher_xera_stats(pid)