# features.py
# Motor Cuantitativo V12.0 (Física Corregida y VMR Empírico)

import numpy as np
from config import PARK_FACTORS

class FeatureEngine:
    
    @staticmethod
    def get_park_factor(venue_id):
        return PARK_FACTORS['runs'].get(venue_id, 1.00)

    def calculate_power_score(self, ops, park_factor, league_avg_runs, team_id, game_date, schedule_data):
        """
        Calcula el Poder Ofensivo Puro.
        Purgado de coeficientes inventados (clima/velocidad) y ruido no calibrado.
        """
        league_ops_base = 0.720
        ops_scale = ops / league_ops_base
        base_runs = ops_scale * league_avg_runs
        
        # El clima y los umpires fueron removidos por ser ruido estadístico (Audit V11.5)
        base_score = base_runs * park_factor

        # Jetlag (A ser corregido en experiments.py en la próxima fase)
        try:
            import experiments
            jetlag_index = experiments.get_jetlag_index(team_id, game_date, schedule_data)
            final_score = experiments.apply_jetlag_penalty(base_score, jetlag_index)
        except Exception:
            final_score = base_score
            
        return final_score

    def calculate_defense_score(self, p_stats, bullpen_stats, fatigue, fielding_stats):
        """
        Cálculo de Prevención de Carreras (Escala RA/9 Directa).
        CORRECCIÓN CRÍTICA: Se eliminó la inversión de escala (9.00 - skill).
        Ahora un número alto significa que el pitcher permite MÁS carreras (peor defensa).
        """
        # Skill del abridor basado en FIP bayesiano (Menos es mejor)
        starter_skill = (p_stats['fip'] * 0.70) + (p_stats['era'] * 0.30)
        
        # Ajuste por ponches: Un K/9 alto reduce el contacto en juego
        starter_ra9 = max(1.0, starter_skill - ((p_stats['k9'] - 7.0) * 0.10))
        
        bullpen_ra9 = bullpen_stats['era']
        if bullpen_stats['whip'] > 1.40: 
            bullpen_ra9 += 0.40 # Castigo por embasar a muchos
        
        # Combinación de Runs Allowed per 9 innings (Abridor 60%, Bullpen 40%)
        prevention_score = (starter_ra9 * 0.60) + (bullpen_ra9 * 0.40)
        
        # Ajuste de Fildeo: Mal fildeo multiplica las carreras permitidas
        fp = fielding_stats['fielding']
        fielding_factor = 1.05 if fp < 0.982 else (0.95 if fp > 0.988 else 1.0)
        
        # La fatiga SUMA carreras esperadas al rival
        final_ra9 = (prevention_score * fielding_factor) + (fatigue * 0.35)
        
        return max(1.5, final_ra9) # Ningún equipo previene menos de 1.5 carreras por juego

    def run_monte_carlo_simulation(self, h_pow, h_def, a_pow, a_def, rounds, league_avg_runs, pf=1.00):
        """
        Motor Estocástico V12.0.
        - BUG RESUELTO: Lambda cruzada (Ofensiva propia vs Defensa rival)
        - VMR EMPÍRICO: Anclado a 1.8 (Literatura Sabermétrica de Hal Stern)
        """
        
        # 1. EL BUG FATAL CORREGIDO: Cruzamos Ofensiva vs Defensa RIVAL
        # a_def y h_def están en escala RA/9. Divididos por la media, crean un escalar.
        # Si el visitante tiene mala defensa (ej. a_def=5.4 frente a media=4.5), su escalar es 1.2
        # Lo que aumentará las carreras anotadas por el local en un 20%.
        a_def_scalar = a_def / league_avg_runs
        h_def_scalar = h_def / league_avg_runs

        # 2. Aplicación de Lambda Correcta y HFA (1.04 Local, 0.96 Visitante)
        h_lambda = (h_pow * a_def_scalar) * 1.04 
        a_lambda = (a_pow * h_def_scalar) * 0.96
        
        # 3. VMR Empírico (Reemplazo del exagerado 2.65 por el documentado 1.8)
        target_vmr = 1.8 * pf 
        
        # 4. Función de muestreo Binomial Negativa
        def nbinom_sample(mu, vmr, size):
            if mu <= 0: return np.zeros(size)
            safe_vmr = max(1.05, vmr) # Protege contra colapso numérico
            r = mu / (safe_vmr - 1.0)
            p = r / (r + mu)
            return np.random.negative_binomial(r, p, size)

        # 5. Generación de Scores
        h_scores = nbinom_sample(h_lambda, target_vmr, rounds)
        a_scores = nbinom_sample(a_lambda, target_vmr, rounds)
        
        # 6. Cálculo Probabilístico
        wins_array = (h_scores > a_scores).astype(float)
        ties_mask = (h_scores == a_scores)
        wins_array[ties_mask] = 0.5 
        
        win_prob = float(np.mean(wins_array))
        
        # 7. Corrección de Incertidumbre
        # El analista demostró que medir el error estándar de las iteraciones es inútil (siempre da ~0%).
        # Ahora exportamos la varianza pura del evento Bernoulli: p * (1 - p)
        bernoulli_variance = win_prob * (1.0 - win_prob)
        
        return win_prob, float(np.mean(h_scores)), float(np.mean(a_scores)), bernoulli_variance