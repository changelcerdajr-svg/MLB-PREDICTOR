# features.py
# Motor Cuantitativo V17.0 (Statcast Real con Termodinámica FanGraphs)

import numpy as np
import math
from scipy.stats import nbinom  # <-- NUEVA IMPORTACIÓN
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
        
        # --- AJUSTE DE SUERTE (BABIP REGRESSION) ---
        # Si el BABIP > 0.300 (tuvo mala suerte), restamos carreras a su xERA (mejorará)
        # Si el BABIP < 0.300 (tuvo buena suerte), sumamos carreras a su xERA (empeorará)
        luck_adjustment = (babip - 0.300) * 2.0 
        starter_xera = base_xera - luck_adjustment
        
        bullpen_era = bullpen_stats.get('fip', 4.10) if bullpen_stats else 4.10
        
        bullpen_fip = bullpen_stats.get('high_leverage_fip', 4.10) if bullpen_stats else 4.10
        
        prevention_score = (starter_xera * 0.70) + (bullpen_fip * 0.30)
        
        if isinstance(fielding_factor, dict):
            ff_value = fielding_factor.get('fielding', 0.985)
        else:
            try: ff_value = float(fielding_factor)
            except (TypeError, ValueError): ff_value = 0.985
                
        capped_fatigue = min(fatigue, 0.45)
        return max(2.0, (prevention_score * ff_value) + capped_fatigue)
    
    def run_monte_carlo_simulation(self, h_pow, h_def, a_pow, a_def, rounds, league_avg_runs, pf=1.00, h_k9=9.0, a_k9=9.0, h_ip=0, a_ip=0, hfa=1.04):
        a_def_scalar = a_def / league_avg_runs
        h_def_scalar = h_def / league_avg_runs

        h_lambda = (h_pow * a_def_scalar) * hfa
        a_lambda = (a_pow * h_def_scalar) * (1.0 / hfa)

        # --- MODELADO DE INCERTIDUMBRE GAUSSIANA V18.0 ---
        # A menos IP, mayor es la campana de Gauss (incertidumbre del talento).
        # Un novato (0 IP) tiene ~25% de error; un veterano (160+ IP) baja al ~5%.
        def calculate_uncertainty(ip):
            return 0.05 + (0.20 * math.exp(-max(0, ip) / 40.0))

        h_unc = calculate_uncertainty(h_ip)
        a_unc = calculate_uncertainty(a_ip)

        # Claridad conceptual cruzada:
        # La incertidumbre del pitcher local (h_unc) afecta las carreras del visitante (a_vol)
        # La incertidumbre del pitcher visitante (a_unc) afecta las carreras del local (h_vol)
        h_vol = a_unc * (9.0 / max(4.0, a_k9))
        a_vol = h_unc * (9.0 / max(4.0, h_k9))

        h_lambda_dist = np.random.normal(h_lambda, h_lambda * h_vol, rounds)
        a_lambda_dist = np.random.normal(a_lambda, a_lambda * a_vol, rounds)
        # --------------------------------------------------
    
        # Ajuste VMR para la Binomial Negativa
        avg_k9 = (h_k9 + a_k9) / 2.0
        k9_adj = 9.0 / max(1.0, avg_k9)
        target_vmr = 1.0 + (0.8 * k9_adj)
        
        def nbinom_sample(mu, vmr):
            mu = np.maximum(mu, 0.001) 
            safe_vmr = max(1.05, vmr) 
            r = mu / (safe_vmr - 1.0)
            p = r / (r + mu)
            # --- FIX ALTO: SciPy nbinom.rvs acepta arrays float para 'r' ---
            return nbinom.rvs(r, p)

        # --- NUEVO: MOTOR DE MARKOV INNING POR INNING (V19.1) ---
        # Dividimos la expectativa total entre 9 entradas
        h_inn_base_lambda = h_lambda_dist / 9.0
        a_inn_base_lambda = a_lambda_dist / 9.0
        
        h_scores = np.zeros(rounds)
        a_scores = np.zeros(rounds)
        
        # Memoria del modelo de Markov (¿Anotó en el inning anterior?)
        h_scored_last = np.zeros(rounds, dtype=bool)
        a_scored_last = np.zeros(rounds, dtype=bool)
        
        # MARKOV BOOST: +15% de probabilidad de anotar si anotaste en el inning previo
        MARKOV_MULTIPLIER = 1.15 
        
        for inn in range(9):
            # Aplicamos la inercia (Momentum intradía)
            h_lambda_cur = np.where(h_scored_last, h_inn_base_lambda * MARKOV_MULTIPLIER, h_inn_base_lambda)
            a_lambda_cur = np.where(a_scored_last, a_inn_base_lambda * MARKOV_MULTIPLIER, a_inn_base_lambda)
            
            # Simulamos las carreras de este inning específico
            h_inn_runs = nbinom_sample(h_lambda_cur, target_vmr)
            a_inn_runs = nbinom_sample(a_lambda_cur, target_vmr)
            
            h_scores += h_inn_runs
            a_scores += a_inn_runs
            
            # Actualizamos la memoria para el siguiente inning
            h_scored_last = h_inn_runs > 0
            a_scored_last = a_inn_runs > 0

        # --- RESOLUCIÓN DE EXTRA INNINGS (Corredor Fantasma) ---
        ties_mask = (h_scores == a_scores)
        while np.any(ties_mask):
            # El corredor en segunda base casi duplica la expectativa de carreras
            h_lambda_ex = h_inn_base_lambda[ties_mask] * 1.8 
            a_lambda_ex = a_inn_base_lambda[ties_mask] * 1.8
            
            h_scores[ties_mask] += nbinom_sample(h_lambda_ex, target_vmr)
            a_scores[ties_mask] += nbinom_sample(a_lambda_ex, target_vmr)
            
            # Volvemos a revisar si siguen empatados
            ties_mask = (h_scores == a_scores)

        # Vector de victorias (ya no hay empates)
        wins_array = (h_scores > a_scores).astype(float)
        
        return float(np.mean(wins_array)), float(np.mean(h_scores)), float(np.mean(a_scores)), float(np.var(wins_array))