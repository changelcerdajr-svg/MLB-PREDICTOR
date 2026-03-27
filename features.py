# features.py
# Motor Cuantitativo V16.0 (Física Corregida para Statcast: xwOBA y xERA)

import numpy as np
from config import PARK_FACTORS

class FeatureEngine:
    
    @staticmethod
    def get_park_factor(venue_id):
        return PARK_FACTORS['runs'].get(venue_id, 1.00)

    def calculate_power_score(self, xwoba, park_factor, league_avg_runs, team_id, game_date, schedule_data):
        """
        Calcula el Poder Ofensivo Puro basado en Calidad de Contacto (xwOBA)
        """
        try:
            pf_value = float(park_factor)
        except (TypeError, ValueError):
            pf_value = 1.0

        # Lógica Statcast
        league_xwoba_base = 0.315
        xwoba_scale = xwoba / league_xwoba_base
        base_runs = xwoba_scale * league_avg_runs
        
        base_score = base_runs * pf_value

        try:
            import experiments
            jetlag_index = experiments.get_jetlag_index(team_id, game_date, schedule_data)
            final_score = experiments.apply_jetlag_penalty(base_score, jetlag_index)
        except Exception:
            final_score = base_score
            
        return final_score

    def calculate_defense_score(self, p_stats, bullpen_stats, fatigue, fielding_factor):
        """
        Calcula el Prevención de Carreras usando Statcast xERA.
        """
        starter_xera = p_stats.get('xera', 4.00) if p_stats else 4.00
        bullpen_era = bullpen_stats.get('era', 4.10) if bullpen_stats else 4.10
        
        prevention_score = (starter_xera * 0.60) + (bullpen_era * 0.40)
        
        if isinstance(fielding_factor, dict):
            ff_value = fielding_factor.get('fielding', 0.985)
        else:
            try:
                ff_value = float(fielding_factor)
            except (TypeError, ValueError):
                ff_value = 0.985
                
        capped_fatigue = min(fatigue, 0.45)
        
        final_ra9 = (prevention_score * ff_value) + capped_fatigue
        return max(2.0, final_ra9)
    
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