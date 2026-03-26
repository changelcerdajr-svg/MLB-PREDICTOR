# model.py
# Orquestador V12.1 (Con Análisis de Sensibilidad de Inputs)
from config import SIMULATION_ROUNDS, STRESS_TEST_ROUNDS
import pickle
import os
from data_loader import MLBDataLoader
from features import FeatureEngine

class MLBPredictor:
    def __init__(self, use_calibrator=True):
        self.loader = MLBDataLoader()
        self.engine = FeatureEngine()
        
        self.calibrator = None
        if use_calibrator:
            try:
                if os.path.exists('isotonic_calibrator.pkl'):
                    with open('isotonic_calibrator.pkl', 'rb') as f:
                        self.calibrator = pickle.load(f)
            except Exception as e:
                print(f"Calibrador no cargado: {e}")
                self.calibrator = None

    def predict_game(self, game):
        # 1. Contexto Temporal y de Liga
        schedule_df = self.loader.get_travel_schedule_window(game['date'], days_back=2)
        league_avg_runs = self.loader.get_league_run_environment(game['date'])
        
        # 2. Pitcheo y Bullpen
        h_pstats = self.loader.get_pitcher_fip_stats(game['home_pitcher'])
        a_pstats = self.loader.get_pitcher_fip_stats(game['away_pitcher'])
        h_bullpen = self.loader.get_bullpen_stats(game['home_id'])
        a_bullpen = self.loader.get_bullpen_stats(game['away_id'])

        if abs(h_pstats['fip'] - 4.30) < 0.001 or abs(a_pstats['fip'] - 4.30) < 0.001:
            return {'error': 'Datos de pitcheo insuficientes o Opener detectado. Simulación abortada.'}

        # 3. Lineups (Compuerta Estricta V12.2)
        h_ops, h_confirmed = self.loader.get_confirmed_lineup_ops(game['id'], 'home')
        a_ops, a_confirmed = self.loader.get_confirmed_lineup_ops(game['id'], 'away')
        
        # SESGO DE DOMINIO RESUELTO: Si no hay lineups, abortamos.
        # No entrenamos ni predecimos con medias ligueras planas (0.720).
        if not h_confirmed or not a_confirmed:
            return {'error': 'Lineups no confirmados. Operación bloqueada para evitar sesgo de dominio.'}

        # 4. Defensa General y Fatiga
        h_fatigue = self.loader.get_bullpen_fatigue(game['home_id'], game['date'])
        a_fatigue = self.loader.get_bullpen_fatigue(game['away_id'], game['date'])
        
        h_fielding = self.loader.get_team_fielding_speed(game['home_id'])
        a_fielding = self.loader.get_team_fielding_speed(game['away_id'])
        
        pf = self.engine.get_park_factor(game['venue_id'])

        # 5. Cálculo de Scores Base
        h_power = self.engine.calculate_power_score(h_ops, pf, league_avg_runs, game['home_id'], game['date'], schedule_df)
        a_power = self.engine.calculate_power_score(a_ops, pf, league_avg_runs, game['away_id'], game['date'], schedule_df)
        
        h_def_ra9 = self.engine.calculate_defense_score(h_pstats, h_bullpen, h_fatigue, h_fielding)
        a_def_ra9 = self.engine.calculate_defense_score(a_pstats, a_bullpen, a_fatigue, a_fielding)

        # 6. Simulación Estocástica Principal
        win_prob, h_runs, a_runs, _ = self.engine.run_monte_carlo_simulation(
            h_pow=h_power, h_def=h_def_ra9, 
            a_pow=a_power, a_def=a_def_ra9, 
            rounds=SIMULATION_ROUNDS, league_avg_runs=league_avg_runs, pf=pf
        )

        # --- 6.5 ANÁLISIS DE SENSIBILIDAD ---
        delta_h = h_ops * 0.05
        delta_a = a_ops * 0.05
        
        h_pow_high = self.engine.calculate_power_score(h_ops + delta_h, pf, league_avg_runs, game['home_id'], game['date'], schedule_df)
        a_pow_low = self.engine.calculate_power_score(a_ops - delta_a, pf, league_avg_runs, game['away_id'], game['date'], schedule_df)
        prob_high, _, _, _ = self.engine.run_monte_carlo_simulation(h_pow_high, h_def_ra9, a_pow_low, a_def_ra9, STRESS_TEST_ROUNDS, league_avg_runs, pf)
        
        h_pow_low = self.engine.calculate_power_score(h_ops - delta_h, pf, league_avg_runs, game['home_id'], game['date'], schedule_df)
        a_pow_high = self.engine.calculate_power_score(a_ops + delta_a, pf, league_avg_runs, game['away_id'], game['date'], schedule_df)
        prob_low, _, _, _ = self.engine.run_monte_carlo_simulation(h_pow_low, h_def_ra9, a_pow_high, a_def_ra9, STRESS_TEST_ROUNDS, league_avg_runs, pf)
        
        # La sensibilidad real: cuánto osciló la probabilidad con este cambio de inputs
        input_sensitivity = abs(prob_high - prob_low) / 2
        
        # 7. Calibración Empírica
        is_calibrated = False
        if self.calibrator is not None:
            win_prob = float(self.calibrator.predict([win_prob])[0])
            is_calibrated = True

        home_win_prob = win_prob
        away_win_prob = 1.0 - win_prob
        winner = game['home_name'] if win_prob > 0.5 else game['away_name']

        # 8. Factor Clave V12.1
        if input_sensitivity > 0.045:
            key = "ALTA FRAGILIDAD (Sensible a ruido ofensivo)"
        elif h_fatigue > 0.25 or a_fatigue > 0.25:
            key = "Fatiga de Bullpen Crítica"
        elif is_calibrated:
            key = "Señal Calibrada"
        else:
            key = "Ventaja Estructural Robusta"

        return {
            'game': f"{game['away_name']} @ {game['home_name']}",
            'winner': winner,
            'home_prob': home_win_prob,
            'away_prob': away_win_prob,
            'confidence': home_win_prob if winner == game['home_name'] else away_win_prob,
            'score': {'home': h_runs, 'away': a_runs, 'total': h_runs + a_runs},
            'details': {
                'sensitivity': f"±{input_sensitivity*100:.1f}% (Riesgo de Error)",
                'pitching': f"H: FIP {h_pstats['fip']:.2f} | A: FIP {a_pstats['fip']:.2f}",
                'fatigue': f"H: {h_fatigue:.2f} | A: {a_fatigue:.2f}",
                'league_env': f"{league_avg_runs:.2f} R/G",
                'lineup': "CONFIRMADO" if (h_confirmed and a_confirmed) else "PROYECTADO"
            },
            'key_factor': key,
            'raw_sensitivity': input_sensitivity
        }
    
    def get_todays_games(self):
        return self.loader.get_schedule()