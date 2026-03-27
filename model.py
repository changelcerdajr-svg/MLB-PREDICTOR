# model.py
# Orquestador V17.0 (Motor Statcast Total: xwOBA y xERA reales)
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
        schedule_df = self.loader.get_travel_schedule_window(game['date'], days_back=2)
        league_avg_runs = self.loader.get_league_run_environment(game['date'])
        
        # 2. Pitcheo con xERA
        h_pstats = self.loader.get_pitcher_xera_stats(game['home_pitcher'])
        a_pstats = self.loader.get_pitcher_xera_stats(game['away_pitcher'])
        
        h_hand = self.loader.get_pitcher_hand(game['home_pitcher'])
        a_hand = self.loader.get_pitcher_hand(game['away_pitcher'])
        
        h_bullpen = self.loader.get_bullpen_stats(game['home_id'])
        a_bullpen = self.loader.get_bullpen_stats(game['away_id'])

        # 3. Lineups con xwOBA
        h_xwoba, h_confirmed = self.loader.get_confirmed_lineup_xwoba(game['id'], 'home')
        a_xwoba, a_confirmed = self.loader.get_confirmed_lineup_xwoba(game['id'], 'away')

        if not h_confirmed or not a_confirmed:
            return {'error': 'Lineups no confirmados. Operación bloqueada para evitar sesgo de dominio.'}

        # 4. Integración de Platoon Splits
        h_split = self.loader.get_team_stats_split(game['home_id'], a_hand)
        a_split = self.loader.get_team_stats_split(game['away_id'], h_hand)
        
        h_xwoba_adj = (h_xwoba * 0.7) + (h_split['woba'] * 0.3)
        a_xwoba_adj = (a_xwoba * 0.7) + (a_split['woba'] * 0.3)

        # 5. Integración de Momentum y Pitagóricas
        h_mom = self.loader.get_team_momentum(game['home_id'], game['date'])
        a_mom = self.loader.get_team_momentum(game['away_id'], game['date'])
        
        h_rs, h_ra = self.loader.get_team_pythagorean_data(game['home_id'], game['date'])
        a_rs, a_ra = self.loader.get_team_pythagorean_data(game['away_id'], game['date'])
        
        def pyth_win_exp(rs, ra):
            return (rs**1.83) / (rs**1.83 + ra**1.83) if (rs + ra) > 0 else 0.500
            
        h_pyth = pyth_win_exp(h_rs, h_ra)
        a_pyth = pyth_win_exp(a_rs, a_ra)

        h_pyth_mult = 1.0 + ((h_pyth - 0.5) * 0.05)
        a_pyth_mult = 1.0 + ((a_pyth - 0.5) * 0.05)

        h_streak_mult = (1.0 + max(-0.05, min(0.05, h_mom['streak'] * 0.01))) * h_pyth_mult
        a_streak_mult = (1.0 + max(-0.05, min(0.05, a_mom['streak'] * 0.01))) * a_pyth_mult

        # 6. Defensa General y Fatiga
        h_fatigue = self.loader.get_bullpen_fatigue(game['home_id'], game['date'])
        a_fatigue = self.loader.get_bullpen_fatigue(game['away_id'], game['date'])
        
        h_fielding = self.loader.get_team_fielding_speed(game['home_id'])
        a_fielding = self.loader.get_team_fielding_speed(game['away_id'])
        
        pf = self.engine.get_park_factor(game['venue_id'])

        # 7. Cálculo de Scores Base con Clima
        weather_data = self.loader.get_weather(game['venue_id'])
        
        h_power = self.engine.calculate_power_score(h_xwoba_adj, pf, league_avg_runs, game['home_id'], game['date'], schedule_df, weather_data, game['venue_id']) * h_streak_mult
        a_power = self.engine.calculate_power_score(a_xwoba_adj, pf, league_avg_runs, game['away_id'], game['date'], schedule_df, weather_data, game['venue_id']) * a_streak_mult
        
        h_def_ra9 = self.engine.calculate_defense_score(h_pstats, h_bullpen, h_fatigue, h_fielding)
        a_def_ra9 = self.engine.calculate_defense_score(a_pstats, a_bullpen, a_fatigue, a_fielding)

        # 8. Simulación Estocástica Principal
        # VMR Ajustado: Reduce la varianza en duelos de pitchers élite (K/9 > 9.0)
        # Si el K/9 promedio es 10.0, la varianza baja un 5%, haciendo la simulación más estable
        avg_k9 = (h_pstats['k9'] + a_pstats['k9']) / 2.0
        k9_vmr_adj = 1.0 + ((8.0 - avg_k9) * 0.025) # Calibración refinada
        win_prob, h_runs, a_runs, _ = self.engine.run_monte_carlo_simulation(
            h_pow=h_power, h_def=h_def_ra9, 
            a_pow=a_power, a_def=a_def_ra9, 
            rounds=SIMULATION_ROUNDS, league_avg_runs=league_avg_runs, pf=pf,
            k9_adj=k9_vmr_adj 
        )

        # 9. Análisis de Sensibilidad (Stress Testing)
        delta_h = h_xwoba_adj * 0.05
        delta_a = a_xwoba_adj * 0.05
        
        h_pow_high = self.engine.calculate_power_score(h_xwoba_adj + delta_h, pf, league_avg_runs, game['home_id'], game['date'], schedule_df, weather_data, game['venue_id']) * h_streak_mult
        a_pow_low = self.engine.calculate_power_score(a_xwoba_adj - delta_a, pf, league_avg_runs, game['away_id'], game['date'], schedule_df, weather_data, game['venue_id']) * a_streak_mult
        prob_high, _, _, _ = self.engine.run_monte_carlo_simulation(h_pow_high, h_def_ra9, a_pow_low, a_def_ra9, STRESS_TEST_ROUNDS, league_avg_runs, pf, k9_adj=k9_vmr_adj)
        
        h_pow_low = self.engine.calculate_power_score(h_xwoba_adj - delta_h, pf, league_avg_runs, game['home_id'], game['date'], schedule_df, weather_data, game['venue_id']) * h_streak_mult
        a_pow_high = self.engine.calculate_power_score(a_xwoba_adj + delta_a, pf, league_avg_runs, game['away_id'], game['date'], schedule_df, weather_data, game['venue_id']) * a_streak_mult
        prob_low, _, _, _ = self.engine.run_monte_carlo_simulation(h_pow_low, h_def_ra9, a_pow_high, a_def_ra9, STRESS_TEST_ROUNDS, league_avg_runs, pf, k9_adj=k9_vmr_adj)
        
        input_sensitivity = abs(prob_high - prob_low) / 2
        
        # 10. Calibración Empírica
        is_calibrated = False
        if self.calibrator is not None:
            win_prob = float(self.calibrator.predict([win_prob])[0])
            is_calibrated = True

        home_win_prob = win_prob
        away_win_prob = 1.0 - win_prob
        winner = game['home_name'] if win_prob > 0.5 else game['away_name']

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
                'sensitivity': f"±{input_sensitivity*100:.1f}% (Riesgo)",
                'pitching': f"H: xERA {h_pstats['xera']:.2f} | A: xERA {a_pstats['xera']:.2f}",
                'fatigue': f"H: {h_fatigue:.2f} | A: {a_fatigue:.2f}",
                'league_env': f"{league_avg_runs:.2f} R/G",
                'lineup': "CONFIRMADO" if (h_confirmed and a_confirmed) else "PROYECTADO"
            },
            'key_factor': key,
            'raw_sensitivity': input_sensitivity
        }
    
    def get_todays_games(self):
        return self.loader.get_schedule()