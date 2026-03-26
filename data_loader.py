# data_loader.py
# Ingesta V10.1 (Bayesian Shrinkage + Dynamic Run Environment)

import requests
import datetime
from config import API_URL, USER_AGENT, USE_REAL_TIME, TEST_DATE, STADIUM_COORDS

# CONSTANTES DE ESTABILIZACIÓN (Basadas en FanGraphs / Tom Tango)
K_BATTER_OPS = 300  # PA necesarios para estabilizar OPS (reemplaza K=100)
K_PITCHER_FIP = 75  # IP necesarios para estabilizar FIP (reemplaza K=18)
LEAGUE_AVG_OPS = 0.720
LEAGUE_AVG_FIP = 4.30

class MLBDataLoader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
        self.standings_cache = {} 
        self.player_history_cache = {} 
        self._force_historical_mode = False  # <--- NUEVA LÍNEA INYECTADA AQUI

    def _get(self, endpoint, params=None):
        try:
            url = f"{API_URL}/{endpoint}"
            r = self.session.get(url, params=params, timeout=6)
            r.raise_for_status()
            return r.json()
        except: return None

    def get_schedule(self, specific_date=None):
        date_str = specific_date if specific_date else (datetime.date.today().strftime("%Y-%m-%d") if USE_REAL_TIME else TEST_DATE)
        self.current_season_year = int(date_str[:4]) 
        
        data = self._get("schedule", {'sportId': 1, 'date': date_str, 'hydrate': 'team,probablePitcher,venue'})
        
        valid = []
        if data and 'dates' in data and len(data['dates']) > 0:
            for g in data['dates'][0]['games']:
                if g.get('gameType') not in ['R', 'P', 'F', 'D', 'L', 'W']: continue
                
                away_score = g['teams']['away'].get('score', 0)
                home_score = g['teams']['home'].get('score', 0)
                status = g['status']['abstractGameState']

                valid.append({
                    'id': g['gamePk'], 'date': date_str,
                    'status': status,
                    'real_score': {'away': away_score, 'home': home_score},
                    'real_winner': g['teams']['home']['team']['name'] if home_score > away_score else g['teams']['away']['team']['name'],
                    'away_id': g['teams']['away']['team']['id'],
                    'home_id': g['teams']['home']['team']['id'],
                    'away_name': g['teams']['away']['team']['name'],
                    'home_name': g['teams']['home']['team']['name'],
                    'venue_id': g['venue']['id'],
                    'away_pitcher': g['teams']['away'].get('probablePitcher', {}).get('id'),
                    'home_pitcher': g['teams']['home'].get('probablePitcher', {}).get('id')
                })
        return valid

    # --- NUEVO V10.1: ENTORNO DINÁMICO ---
    def get_league_run_environment(self, date_str):
        """
        Calcula cuántas carreras promedia la liga hasta la fecha dada.
        Reemplaza al '4.5' fijo.
        """
        # Si ya tenemos caché de standings para esa fecha, úsalo (optimización básica)
        # Para V10.1 haremos la llamada directa para asegurar precisión
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
                        games = wins + losses
                        
                        total_runs += runs
                        total_games += games
            
            if total_games > 0:
                # Promedio por equipo por juego
                league_avg = total_runs / total_games
                
                # Soft Shrinkage para inicio de temporada (<200 juegos totales en la liga)
                if total_games < 200: 
                    weight = total_games / 200
                    league_avg = (league_avg * weight) + (4.30 * (1 - weight))
                
                return league_avg
                
        except: pass
        return 4.30 # Fallback seguro

    # --- MOTOR BAYESIANO V10.0 ---
    def _apply_bayesian_shrinkage(self, current_val, sample_size, k_factor, prior_val):
        if sample_size <= 0: return prior_val
        weight = sample_size / (sample_size + k_factor)
        return (current_val * weight) + (prior_val * (1 - weight))

    def _get_prior_stats(self, pid, stat_group):
        cache_key = f"{pid}_{stat_group}_{self.current_season_year-1}"
        if cache_key in self.player_history_cache:
            return self.player_history_cache[cache_key]

        prev_year = self.current_season_year - 1
        try:
            data = self._get(f"people/{pid}/stats", {'stats': 'season', 'group': stat_group, 'season': prev_year})
            if data and 'stats' in data and data['stats'] and data['stats'][0].get('splits'):
                stat = data['stats'][0]['splits'][0]['stat']
                if stat_group == 'hitting':
                    res = float(stat.get('ops', LEAGUE_AVG_OPS))
                else:
                    ip = float(stat.get('inningsPitched', 1.0))
                    if ip > 10:
                        hr = int(stat.get('homeRuns', 0))
                        bb = int(stat.get('baseOnBalls', 0))
                        k = int(stat.get('strikeouts', 0))
                        res = ((13 * hr) + (3 * bb) - (2 * k)) / ip + 3.20
                    else:
                        res = float(stat.get('era', LEAGUE_AVG_FIP))
                self.player_history_cache[cache_key] = res
                return res
        except: pass
        default = LEAGUE_AVG_OPS if stat_group == 'hitting' else LEAGUE_AVG_FIP
        self.player_history_cache[cache_key] = default
        return default

    # --- EXTRACTORES ---
    def get_pitcher_fip_stats(self, pid):
        stats = {'era': 4.50, 'fip': LEAGUE_AVG_FIP, 'k9': 7.5} 
        if not pid: return stats
        try:
            d = self._get(f"people/{pid}/stats", {'stats': 'season', 'group': 'pitching'})
            current_fip = LEAGUE_AVG_FIP
            current_ip = 0.0
            current_era = 4.50
            current_k9 = 7.5

            if d and 'stats' in d and d['stats'] and d['stats'][0].get('splits'):
                s = d['stats'][0]['splits'][0]['stat']
                current_ip = float(s.get('inningsPitched', 0.0))
                current_era = float(s.get('era', 4.50))
                current_k9 = float(s.get('strikeoutsPer9Inn', 7.5))
                hr = int(s.get('homeRuns', 0))
                bb = int(s.get('baseOnBalls', 0))
                hbp = int(s.get('hitByPitch', 0))
                k = int(s.get('strikeouts', 0))
                if current_ip > 0.1:
                    current_fip = ((13 * hr) + (3 * (bb + hbp)) - (2 * k)) / current_ip + 3.20
                else: current_fip = current_era

            prior_fip = self._get_prior_stats(pid, 'pitching')
            projected_fip = self._apply_bayesian_shrinkage(current_fip, current_ip, K_PITCHER_FIP, prior_fip)
            stats = {'era': current_era, 'fip': projected_fip, 'k9': current_k9}
        except: pass
        return stats

    def get_confirmed_lineup_ops(self, game_pk, team_type):
        try:
            box = self._get(f"game/{game_pk}/boxscore")
            if not box: return (None, False)
            batters_ids = box['teams'][team_type].get('battingOrder', [])
            if not batters_ids: return (None, False)
            
            ids_str = ",".join([str(x) for x in batters_ids])
            people_data = self._get(f"people", {'personIds': ids_str, 'hydrate': 'stats(group=[hitting],type=[season])'})
            
            ops_map = {}
            if people_data and 'people' in people_data:
                for p in people_data['people']:
                    pid = p['id']
                    current_ops = LEAGUE_AVG_OPS
                    current_ab = 0
                    s = p.get('stats', [])
                    if s and s[0].get('splits'):
                        stat = s[0]['splits'][0]['stat']
                        current_ab = int(stat.get('atBats', 0))
                        current_ops = float(stat.get('ops', LEAGUE_AVG_OPS))
                    
                    prior_ops = self._get_prior_stats(pid, 'hitting')
                    projected_ops = self._apply_bayesian_shrinkage(current_ops, current_ab, K_BATTER_OPS, prior_ops)
                    ops_map[pid] = projected_ops

            weights = [1.32, 1.28, 1.15, 1.05, 1.00, 0.92, 0.85, 0.78, 0.65] 
            weighted_sum = 0
            total_weight = 0
            for i, pid in enumerate(batters_ids):
                if i < len(weights):
                    w = weights[i]
                    p_ops = ops_map.get(pid, LEAGUE_AVG_OPS)
                    weighted_sum += (p_ops * w)
                    total_weight += w
            if total_weight > 0: 
                return (weighted_sum / total_weight, True)
        except Exception as e: 
            pass
            
        # Si no encontró lineups reales en la API, falla con dignidad. No más datos falsos.
        return (None, False)

    def get_team_fielding_speed(self, team_id):
        res = {'fielding': 0.985, 'sb_game': 0.5} 
        try:
            f_data = self._get(f"teams/{team_id}/stats", {'stats': 'season', 'group': 'fielding'})
            if f_data and 'stats' in f_data and f_data['stats'] and f_data['stats'][0].get('splits'):
                res['fielding'] = float(f_data['stats'][0]['splits'][0]['stat'].get('fielding', 0.985))
            h_data = self._get(f"teams/{team_id}/stats", {'stats': 'season', 'group': 'hitting'})
            if h_data and 'stats' in h_data and h_data['stats'] and h_data['stats'][0].get('splits'):
                s = h_data['stats'][0]['splits'][0]['stat']
                sb = int(s.get('stolenBases', 0))
                games = int(s.get('gamesPlayed', 1))
                res['sb_game'] = sb / max(1, games)
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
                whip = float(s.get('whip', 1.30))
                if ip < 20:
                    w = ip / 30.0 
                    era = (era * w) + (4.00 * (1-w))
                    whip = (whip * w) + (1.30 * (1-w))
                stats['era'] = era
                stats['whip'] = whip
        except: pass
        return stats

    def get_team_stats_split(self, team_id, opponent_hand):
        stats = {'ops': 0.700}
        try:
            split_code = "vsL" if opponent_hand == 'L' else "vsR"
            data = self._get(f"teams/{team_id}/stats", {'stats': 'vsOpponents', 'group': 'hitting', 'sitCodes': split_code})
            if data and 'stats' in data and data['stats'] and data['stats'][0].get('splits'):
                stats['ops'] = float(data['stats'][0]['splits'][0]['stat'].get('ops', 0.700))
        except: pass
        return stats
    
    def get_team_pythagorean_data(self, team_id):
        try:
            data = self._get("standings", {'leagueId': '103,104', 'season': self.current_season_year}) 
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
        except: 
            return {'l10': 0.5, 'streak': 0}

    def get_bullpen_fatigue(self, team_id, game_date):
        """
        V11.6: Rastreador de Fatiga (Parche Opening Day).
        Mira 3 días atrás, ignora Spring Training y protege el inicio de temporada.
        """
        fatigue_score = 0.0
        try:
            # Importar datetime si no está en el scope local (aunque ya lo tienes arriba)
            import datetime 
            date_obj = datetime.datetime.strptime(game_date, "%Y-%m-%d")
            
            # PARCHE DE OPENING DAY:
            # Si el juego es en marzo o la primera semana de abril, el bullpen está fresco.
            if date_obj.month == 3 or (date_obj.month == 4 and date_obj.day <= 7):
                return 0.0 
                
            for i in range(1, 4): 
                prev_date = (date_obj - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
                
                # Buscamos juegos regulares (gameType='R')
                data = self._get("schedule", {'sportId': 1, 'date': prev_date, 'teamId': team_id, 'gameType': 'R'})
                
                if data and 'dates' in data and data['dates']:
                    for g in data['dates'][0]['games']:
                        if g['status']['abstractGameState'] == 'Final':
                            is_home = g['teams']['home']['team']['id'] == team_id
                            runs_allowed = g['teams']['home']['score'] if not is_home else g['teams']['away']['score']
                            
                            # Si permitieron > 5 carreras, el bullpen trabajó de más
                            if runs_allowed > 5: 
                                fatigue_score += 0.12
                            fatigue_score += 0.08 # Cansancio base por jugar
            
            return min(0.4, fatigue_score) 
        except Exception as e:
            # Silenciamos el error para no romper la predicción, asumimos fatiga leve
            return 0.1
    def get_pitcher_hand(self, pid):
        if not pid: return 'R'
        try:
            d = self._get(f"people/{pid}")
            if d and 'people' in d and len(d['people']) > 0:
                return d['people'][0]['pitchHand']['code']
        except: pass
        return 'R'
    def get_travel_schedule_window(self, target_date_str, days_back=2):
        """
        Extrae un calendario rodante para evaluar viajes y jetlag correctamente.
        """
        import datetime
        target_date = datetime.datetime.strptime(target_date_str, "%Y-%m-%d")
        start_date = (target_date - datetime.timedelta(days=days_back)).strftime("%Y-%m-%d")
        
        data = self._get("schedule", {'sportId': 1, 'startDate': start_date, 'endDate': target_date_str})
        
        # Formateamos los datos crudos a una lista de diccionarios fácil de leer para Pandas
        schedule_list = []
        if data and 'dates' in data:
            for date_item in data['dates']:
                d_str = date_item['date']
                for g in date_item['games']:
                    if g.get('gameType') in ['R', 'P', 'F', 'D', 'L', 'W']:
                        schedule_list.append({
                            'date': d_str,
                            'away_team': g['teams']['away']['team']['id'],
                            'home_team': g['teams']['home']['team']['id']
                        })
        
        import pandas as pd
        return pd.DataFrame(schedule_list)
    
    def get_weather(self, vid):
        c = STADIUM_COORDS.get(vid, {'lat': 40, 'lon': -80})
        try:
            d = requests.get("https://api.open-meteo.com/v1/forecast", params={'latitude':c['lat'], 'longitude':c['lon'], 'current_weather':'true'}, timeout=3).json()
            return d['current_weather']
        except: return {'temperature': 20, 'windspeed': 5}
    def get_pitcher_stats(self, pid): return self.get_pitcher_fip_stats(pid)