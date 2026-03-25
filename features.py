# features.py
# Motor Cuantitativo V11.5 (Física y Estocástica Purificadas)

import numpy as np
from config import PARK_FACTORS

class FeatureEngine:
    
    @staticmethod
    def get_park_factor(venue_id):
        return PARK_FACTORS['runs'].get(venue_id, 1.00)

    def calculate_pythagorean_win_pct(self, rs, ra):
        if rs == 0 and ra == 0: return 0.500
        rs_pow = pow(rs, 1.83)
        ra_pow = pow(ra, 1.83)
        return rs_pow / (rs_pow + ra_pow)

    def calculate_power_score(self, ops, park_factor, weather_temp, wind_speed, umpire_factor, speed_stats, league_avg_runs, team_id, game_date, schedule_data):
        """
        Calcula el Poder Ofensivo Puro.
        Purgado de step-functions y ruido meteorológico no vectorial.
        """
        league_ops_base = 0.720
        ops_scale = ops / league_ops_base
        base_runs = ops_scale * league_avg_runs
        
        # 1. Velocidad (Suavizada): Reemplazamos el step-function por un escalado continuo
        # Maximo impacto de 2.5% para equipos extremadamente rápidos, sin saltos abruptos.
        sb_rate = min(max(speed_stats.get('sb_game', 0), 0), 2.5)
        speed_boost = 1.0 + (sb_rate * 0.01)
        
        # 2. Clima Termodinámico: Base 21C, con piso matemático seguro.
        # El viento se ignora estructuralmente porque carecemos de vector/dirección.
        weather_impact = max(0.85, 1.0 + ((weather_temp - 21.0) * 0.003))
        
        base_score = (base_runs * park_factor * weather_impact * umpire_factor * speed_boost)

        # 3. Jetlag (Ventana Rodante Estricta)
        try:
            import experiments
            jetlag_index = experiments.get_jetlag_index(team_id, game_date, schedule_data)
            final_score = experiments.apply_jetlag_penalty(base_score, jetlag_index)
        except Exception:
            final_score = base_score
            
        return final_score

    def calculate_defense_score(self, p_stats, bullpen_stats, fatigue, umpire_factor, fielding_stats):
        """
        Cálculo de Prevención de Carreras.
        """
        starter_skill = (p_stats['fip'] * 0.70) + (p_stats['era'] * 0.30)
        starter_prevention = max(0, 9.00 - starter_skill) + (p_stats['k9'] - 7.0) * 0.10
        
        bullpen_prevention = max(0, 9.00 - bullpen_stats['era'])
        if bullpen_stats['whip'] > 1.40: bullpen_prevention -= 0.4
        
        prevention_score = (starter_prevention * 0.60) + (bullpen_prevention * 0.40)
        
        fp = fielding_stats['fielding']
        fielding_factor = 0.94 if fp < 0.982 else (1.04 if fp > 0.988 else 1.0)
        
        # La fatiga resta capacidad defensiva 
        # (Delta empírico: un bullpen exhausto (1.0) añade ~0.35 carreras al RA/9 esperado)
        final_prevention = (prevention_score * fielding_factor) - (fatigue * 0.35)
        return max(0.1, final_prevention * (2.0 - umpire_factor))

    def run_monte_carlo_simulation(self, h_pow, h_def, a_pow, a_def, rounds, league_avg_runs, pf=1.00):
        """
        Motor Estocástico V11.5. 
        Implementa HFA explícita y parameterización NegBinomial dinámica.
        """
        
        # 1. Aplicación de Home Field Advantage (HFA) Derivada
        # Para VMR 2.65, k=1.045 genera el 53.5% de win rate histórico.
        h_lambda = (h_pow * (h_def / league_avg_runs)) * 1.045
        a_lambda = (a_pow * (a_def / league_avg_runs)) * 0.955
        
        # 2. VMR Dinámico basado en el Parque
        # La varianza crece proporcionalmente al factor de carreras del estadio.
        target_vmr = 2.65 * pf 
        
        # 3. Función de muestreo Binomial Negativa
        def nbinom_sample(mu, vmr, size):
            if mu <= 0: return np.zeros(size)
            # Aseguramos un VMR > 1 para mantener la dispersión de colas largas
            # La fórmula r = mu / (VMR - 1) define la 'forma' de la distribución
            safe_vmr = max(1.1, vmr)
            r = mu / (safe_vmr - 1.0)
            p = r / (r + mu)
            return np.random.negative_binomial(r, p, size)

        # 4. Generación de Scores
        h_scores = nbinom_sample(h_lambda, target_vmr, rounds)
        a_scores = nbinom_sample(a_lambda, target_vmr, rounds)
        
        # 5. Cálculo de Probabilidades e Incertidumbre
        wins_array = (h_scores > a_scores).astype(float)
        ties_mask = (h_scores == a_scores)
        wins_array[ties_mask] = 0.5 # Los empates se dividen (Regla de paridad)
        
        chunks = np.array_split(wins_array, 10)
        chunk_probs = [np.mean(c) for c in chunks]
        
        uncertainty = float(np.std(chunk_probs)) 
        win_prob = float(np.mean(wins_array))
        
        return win_prob, float(np.mean(h_scores)), float(np.mean(a_scores)), uncertainty