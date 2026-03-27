# features.py
# Motor Cuantitativo V17.0 (Statcast Real con Termodinámica FanGraphs)

import numpy as np
import math
from config import PARK_FACTORS

# Base empírica de orientaciones (Grados desde el Norte geográfico hacia el CF)
STADIUM_AZIMUTHS = {
    1: 45, 2: 45, 3: 180, 5: 45, 7: 135, 8: 135, 9: 45, 10: 45, 
    11: 135, 12: 135, 13: 45, 14: 45, 15: 0, 17: 45, 18: 90, 19: 0, 
    21: 45, 22: 180, 24: 90, 28: 135, 31: 45, 32: 65, 33: 340,
}

class FeatureEngine:
    
    @staticmethod
    def get_park_factor(venue_id):
        return PARK_FACTORS['runs'].get(venue_id, 1.00)

    def calculate_weather_multiplier(self, venue_id, weather_data):
        if not weather_data: return 1.0

        temp_c = weather_data.get('temperature', 21.0)
        wind_speed_kmh = weather_data.get('windspeed', 0.0)
        wind_dir = weather_data.get('winddirection', 45.0)

        # Temp: +1 grado C = +0.4% incremento en carreraje
        temp_adj = 1.0 + ((temp_c - 21.0) * 0.004)

        wind_speed_mph = wind_speed_kmh / 1.609
        blowing_to = (wind_dir + 180) % 360
        
        azimuth = STADIUM_AZIMUTHS.get(venue_id, 45)
        angle_rad = math.radians(blowing_to - azimuth)
        effective_wind = wind_speed_mph * math.cos(angle_rad)

        # Coeficiente empírico validado: ~0.4% por mph de viento efectivo
        wind_adj = 1.0 + (effective_wind * 0.004)

        return max(0.85, min(1.20, temp_adj * wind_adj))

    def calculate_power_score(self, xwoba, park_factor, league_avg_runs, team_id, game_date, schedule_data, weather_data=None, venue_id=1):
        try: pf_value = float(park_factor)
        except (TypeError, ValueError): pf_value = 1.0

        weather_multiplier = self.calculate_weather_multiplier(venue_id, weather_data)

        # Lógica Statcast real
        league_xwoba_base = 0.315
        xwoba_scale = xwoba / league_xwoba_base
        base_runs = xwoba_scale * league_avg_runs
        
        base_score = base_runs * pf_value * weather_multiplier

        try:
            import experiments
            jetlag_index = experiments.get_jetlag_index(team_id, game_date, schedule_data)
            final_score = experiments.apply_jetlag_penalty(base_score, jetlag_index)
        except Exception: final_score = base_score
            
        return final_score

    def calculate_defense_score(self, p_stats, bullpen_stats, fatigue, fielding_factor):
        # Lógica Statcast real
        starter_xera = p_stats.get('xera', 4.00) if p_stats else 4.00
        bullpen_era = bullpen_stats.get('era', 4.10) if bullpen_stats else 4.10
        prevention_score = (starter_xera * 0.60) + (bullpen_era * 0.40)
        
        if isinstance(fielding_factor, dict):
            ff_value = fielding_factor.get('fielding', 0.985)
        else:
            try: ff_value = float(fielding_factor)
            except (TypeError, ValueError): ff_value = 0.985
                
        capped_fatigue = min(fatigue, 0.45)
        return max(2.0, (prevention_score * ff_value) + capped_fatigue)
    
    def run_monte_carlo_simulation(self, h_pow, h_def, a_pow, a_def, rounds, league_avg_runs, pf=1.00, k9_adj=1.0):
        a_def_scalar = a_def / league_avg_runs
        h_def_scalar = h_def / league_avg_runs

        h_lambda = (h_pow * a_def_scalar) * 1.04 
        a_lambda = (a_pow * h_def_scalar) * 0.96
        
        target_vmr = 1.8 * pf * max(0.92, min(1.08, k9_adj)) 
        
        def nbinom_sample(mu, vmr, size):
            if mu <= 0: return np.zeros(size)
            safe_vmr = max(1.05, vmr) 
            r = mu / (safe_vmr - 1.0)
            p = r / (r + mu)
            return np.random.negative_binomial(r, p, size)

        h_scores = nbinom_sample(h_lambda, target_vmr, rounds)
        a_scores = nbinom_sample(a_lambda, target_vmr, rounds)
        
        wins_array = (h_scores > a_scores).astype(float)
        ties_mask = (h_scores == a_scores)
        wins_array[ties_mask] = 0.5 
        
        win_prob = float(np.mean(wins_array))
        bernoulli_variance = win_prob * (1.0 - win_prob)
        
        return win_prob, float(np.mean(h_scores)), float(np.mean(a_scores)), bernoulli_variance