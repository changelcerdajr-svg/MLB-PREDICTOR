# features.py
# Motor Cuantitativo V17.0 (Statcast Real con Termodinámica FanGraphs)

import numpy as np
import math
from scipy.stats import nbinom
import config 
from config import PARK_FACTORS

# Base empírica de orientaciones (Grados desde el Norte geográfico hacia el CF)
# Grados desde el Norte geográfico (0°) hacia el Center Field
# Sincronizado con los Venue IDs oficiales de la API de MLB
STADIUM_AZIMUTHS = {
    1: 45,    # Angel Stadium (LAA) - NE
    2: 45,    # Oriole Park (BAL) - NE
    3: 180,   # Tropicana Field (TB) - Domo (S)
    5: 45,    # Progressive Field (CLE) - NE
    7: 135,   # Kauffman Stadium (KC) - SE
    8: 135,   # Comerica Park (DET) - SE
    9: 45,    # Fenway Park (BOS) - NE
    10: 45,   # Rogers Centre (TOR) - NE
    11: 135,  # T-Mobile Park (SEA) - SE
    12: 135,  # Guaranteed Rate Field (CWS) - SE
    13: 45,   # Target Field (MIN) - NE
    14: 45,   # Oakland Coliseum (OAK) - NE
    15: 0,    # Chase Field (AZ) - N
    16: 90,   # Truist Park (ATL) - E
    17: 45,   # Wrigley Field (CHC) - NE
    18: 90,   # Great American Ball Park (CIN) - E
    19: 0,    # Coors Field (COL) - N
    20: 45,   # American Family Field (MIL) - NE
    21: 45,   # Citizens Bank Park (PHI) - NE
    22: 180,  # Dodger Stadium (LAD) - S
    23: 135,  # Nationals Park (WSH) - SE
    24: 90,   # Oracle Park (SF) - E
    25: 45,   # Petco Park (SD) - NE
    26: 45,   # Busch Stadium (STL) - NE
    27: 45,   # Globe Life Field (TEX) - NE
    29: 45,   # loanDepot park (MIA) - NE
    30: 135,  # PNC Park (PIT) - SE
    31: 45,   # Citi Field (NYM) - NE
    32: 65,   # Yankee Stadium (NYY) - ENE
    33: 340,  # Minute Maid Park (HOU) - NNW
}

class FeatureEngine:
    @staticmethod
    def get_park_factor(venue_id):
        return PARK_FACTORS['runs'].get(venue_id, 1.00)

    def calculate_weather_multiplier(self, venue_id, weather_data):
        # Filtro A1: Domos y estadios con techo retráctil no sufren alteraciones de clima
        DOME_VENUES = {3, 10, 15, 20, 27, 33}
        if venue_id in DOME_VENUES:
            return 1.0

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
        base_xera = p_stats.get('xera', 4.00) if p_stats else 4.00
        babip = p_stats.get('babip', 0.300) if p_stats else 0.300
        era_real = p_stats.get('era', None) if p_stats else None
        
        # --- NUEVO: Extraemos K/9 del diccionario (promedio 7.5 si falla) ---
        sp_k9 = p_stats.get('k9', 7.5) if p_stats else 7.5 
        
        # --- FIX ALTO: Evitar doble correccion de suerte ---
        if era_real and not p_stats.get('xera'):
            luck_adjustment = (babip - 0.300) * 2.0
            starter_xera = era_real - luck_adjustment
        else:
            starter_xera = base_xera # xERA ya elimina la suerte del BABIP
            
        bullpen_fip = bullpen_stats.get('high_leverage_fip', 4.10) if bullpen_stats else 4.10
        
        # =====================================================================
        # CIRUGÍA CUANTITATIVA: Peso Dinámico y Penalización por K/9
        # =====================================================================
        # 1. Dinámica de Entradas (Innings) basada en Talento
        if starter_xera < 3.50:
            sp_weight = 0.65 # Pitcher élite lanza 6+ innings
        elif starter_xera > 4.50:
            sp_weight = 0.50 # Pitcher débil explota temprano, expone al bullpen
        else:
            sp_weight = 0.58 # Promedio
            
        # 2. Penalización por Varianza (El Factor K/9)
        k9_penalty = 0.0
        if sp_k9 < 7.0:
            k9_penalty = 0.25 # Peligroso: Depende mucho de la defensa (Ej. Mets)
        elif sp_k9 > 9.5:
            k9_penalty = -0.15 # Élite: Elimina la varianza del juego (Ej. D-Backs)
            
        # 3. xERA Ajustado
        adjusted_sp_xera = starter_xera + k9_penalty
        bp_weight = 1.0 - sp_weight
        
        # 4. Mezcla Final Dinámica
        prevention_score = (adjusted_sp_xera * sp_weight) + (bullpen_fip * bp_weight)
        # =====================================================================
        
        if isinstance(fielding_factor, dict):
            ff_value = fielding_factor.get('fielding', 0.985)
        else:
            try: ff_value = float(fielding_factor)
            except (TypeError, ValueError): ff_value = 0.985
                
        capped_fatigue = min(fatigue, 0.45)
        return max(2.0, (prevention_score * ff_value) + capped_fatigue)
    
    def run_monte_carlo_simulation(self, h_pow, h_def, a_pow, a_def, rounds, league_avg_runs, h_k9=9.0, a_k9=9.0, h_ip=0, a_ip=0, hfa=1.04):
        a_def_scalar = a_def / league_avg_runs
        h_def_scalar = h_def / league_avg_runs

        h_lambda = (h_pow * a_def_scalar) * hfa
        a_lambda = (a_pow * h_def_scalar) * (1.0 / hfa)

        # FIX ALTO 4: Reducir piso de incertidumbre y acelerar decaimiento
        def calculate_uncertainty(ip):
            return 0.02 + (0.12 * math.exp(-max(0, ip) / 25.0))

        h_unc = calculate_uncertainty(h_ip)
        a_unc = calculate_uncertainty(a_ip)

        # FIX CRÍTICO 1: Lambdas deterministas (eliminar ruido Normal extra)
        h_lambda_dist = np.full(rounds, h_lambda)
        a_lambda_dist = np.full(rounds, a_lambda)
        
        # Necesitamos el lambda base dividido por 9 innings
        h_inn_base_lambda = h_lambda_dist / 9.0
        a_inn_base_lambda = a_lambda_dist / 9.0
    
        # FIX CRÍTICO 5 (VMR Asimétrico integrado): La varianza depende del pitcher rival
        h_target_vmr = 1.0 + (0.6 * a_k9/9.0) * (1.0 + a_unc * 0.5)
        a_target_vmr = 1.0 + (0.6 * h_k9/9.0) * (1.0 + h_unc * 0.5)
        
        def nbinom_sample(mu, vmr):
            mu = np.maximum(mu, 0.001) 
            safe_vmr = max(1.05, vmr) 
            r = mu / (safe_vmr - 1.0)
            p = r / (r + mu)
            return nbinom.rvs(r, p)
        
        h_scores = np.zeros(rounds)
        a_scores = np.zeros(rounds)
        
        h_scored_last = np.zeros(rounds, dtype=bool)
        a_scored_last = np.zeros(rounds, dtype=bool)
        
        for inn in range(9):
            # ACCESO DINÁMICO
            h_lambda_cur = np.where(h_scored_last, h_inn_base_lambda * config.MARKOV_MULTIPLIER, h_inn_base_lambda)
            a_lambda_cur = np.where(a_scored_last, a_inn_base_lambda * config.MARKOV_MULTIPLIER, a_inn_base_lambda)
            
            # Usar los VMR asimétricos correctamente
            h_inn_runs = nbinom_sample(h_lambda_cur, h_target_vmr)
            a_inn_runs = nbinom_sample(a_lambda_cur, a_target_vmr)
            
            h_scores += h_inn_runs
            a_scores += a_inn_runs
            
            h_scored_last = h_inn_runs > 0
            a_scored_last = a_inn_runs > 0

        ties_mask = (h_scores == a_scores)
        
        MAX_EXTRA = 12
        for _ in range(MAX_EXTRA):
            if not np.any(ties_mask):
                break 
            
            h_lambda_ex = h_inn_base_lambda[ties_mask] * config.EXTRA_INNING_MULTIPLIER
            a_lambda_ex = a_inn_base_lambda[ties_mask] * config.EXTRA_INNING_MULTIPLIER
            
            # Usar los VMR asimétricos correctamente en Extra Innings
            h_scores[ties_mask] += nbinom_sample(h_lambda_ex, h_target_vmr)
            a_scores[ties_mask] += nbinom_sample(a_lambda_ex, a_target_vmr)
            
            ties_mask = (h_scores == a_scores)

        if np.any(ties_mask):
            num_ties = ties_mask.sum()
            residual_winners = np.random.choice([0.0, 1.0], size=num_ties)
            h_scores[ties_mask] += residual_winners
            a_scores[ties_mask] += (1.0 - residual_winners)

        wins_array = (h_scores > a_scores).astype(float)
        
        return float(np.mean(wins_array)), float(np.mean(h_scores)), float(np.mean(a_scores)), float(np.var(wins_array))