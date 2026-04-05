# model.py
# Orquestador V17.9 (Motor Statcast Total + Volatilidad K/9)
from config import SIMULATION_ROUNDS, STRESS_TEST_ROUNDS, get_hfa_factor # <-- Todos juntos aquí
import pickle
import os
from data_loader import MLBDataLoader
from features import FeatureEngine

class MLBPredictor:
    def __init__(self, use_calibrator=True, use_hot_hand=True, experiments=None):
        self.loader = MLBDataLoader()
        self.engine = FeatureEngine()
        self.use_hot_hand = use_hot_hand
        
        # Si no se mandan experimentos, todo está encendido por defecto
        self.active_features = experiments or {
            'jetlag': True, 'weather': True, 'trajectory': True, 'markov': True
        }
        
        self.calibrator = None
        if use_calibrator:
            try:
                if os.path.exists('temperature_calibrator.pkl'):
                    with open('temperature_calibrator.pkl', 'rb') as f:
                        self.calibrator = pickle.load(f)
            except Exception as e:
                print(f"Calibrador no cargado: {e}")
                self.calibrator = None

    def predict_game(self, game):
        # 1. Preparación de Entorno
        schedule_df = self.loader.get_travel_schedule_window(game['date'], days_back=5)
        league_avg_runs = self.loader.get_league_run_environment(game['date'])
        
        # Extraemos el año desde la fecha del juego directamente
        game_year = int(game['date'][:4])
        
        # 2. Pitcheo con xERA, K/9 e IP para Incertidumbre (Forzando el año)
        h_pstats = self.loader.get_pitcher_xera_stats(game['home_pitcher'], year=game_year)
        a_pstats = self.loader.get_pitcher_xera_stats(game['away_pitcher'], year=game_year)
        
        h_k9 = h_pstats.get('k9', 9.0)
        a_k9 = a_pstats.get('k9', 9.0)
        h_ip = h_pstats.get('ip', 0.0)  # <--- NUEVO
        a_ip = a_pstats.get('ip', 0.0)  # <--- NUEVO
        
        h_hand = self.loader.get_pitcher_hand(game['home_pitcher'])
        a_hand = self.loader.get_pitcher_hand(game['away_pitcher'])
        
        # FIX: Pasarle la fecha para que el caché funcione correctamente
        h_bullpen = self.loader.get_bullpen_stats(game['home_id'], game['date'])
        a_bullpen = self.loader.get_bullpen_stats(game['away_id'], game['date'])

        # 3. Lineups con xwOBA Real (Platoon Proxy V17.9)
        h_xwoba, h_confirmed = self.loader.get_confirmed_lineup_xwoba(
        game['id'], 'home', vs_hand=a_hand, 
        use_hot_hand=self.use_hot_hand 
        )
        
        a_xwoba, a_confirmed = self.loader.get_confirmed_lineup_xwoba(
        game['id'], 'away', vs_hand=h_hand,
        use_hot_hand=self.use_hot_hand 
        )

        if not h_confirmed or not a_confirmed:
            return {'error': 'Lineups no confirmados. Operación bloqueada.'}

        # 4. Señal Real (Sin Ponderaciones Antiguas)
        h_xwoba_adj = h_xwoba 
        a_xwoba_adj = a_xwoba

        # --- REESTRUCTURACIÓN M4 ---
        # 5a. Obtenemos el Park Factor primero para usarlo en la balística
        pf = self.engine.get_park_factor(game['venue_id'])
        weather_data = self.loader.get_weather(game['venue_id'])

        # Extraemos el año actual del entorno del juego
        current_year = self.loader.current_season_year

        # 5a. Obtenemos el Park Factor y Clima
        pf = self.engine.get_park_factor(game['venue_id'])
        
        # INTERRUPTOR CLIMA: Si está apagado, weather_data será None
        weather_data = None
        if self.active_features.get('weather', True):
            weather_data = self.loader.get_weather(game['venue_id'])

        # Extraemos el año actual del entorno del juego
        current_year = self.loader.current_season_year

        # 5b. Ajustes Biomecánicos y Balísticos (Contextualizados al Estadio)
        h_pitcher_goao = self.loader.get_batted_ball_profile(game['home_pitcher'], current_year, is_pitcher=True)
        a_pitcher_goao = self.loader.get_batted_ball_profile(game['away_pitcher'], current_year, is_pitcher=True)
        h_team_goao = self.loader.get_batted_ball_profile(game['home_id'], current_year, is_pitcher=False)
        a_team_goao = self.loader.get_batted_ball_profile(game['away_id'], current_year, is_pitcher=False)

        def calculate_trajectory_multiplier(pitcher_goao, team_goao):
            diff = (team_goao - pitcher_goao)
            # MANTENEMOS FIX Feature #23: Coeficiente 0.025 conservador
            multiplier = 1.0 + (diff * 0.025)
            return max(0.95, min(1.05, multiplier))

        h_traj_mult = calculate_trajectory_multiplier(a_pitcher_goao, h_team_goao)
        a_traj_mult = calculate_trajectory_multiplier(h_pitcher_goao, a_team_goao)

        # INTERRUPTOR TRAYECTORIA: Si está apagado, forzamos a 1.0 (neutro)
        if not self.active_features.get('trajectory', True):
            h_traj_mult, a_traj_mult = 1.0, 1.0

        h_xwoba_adj = h_xwoba * h_traj_mult
        a_xwoba_adj = a_xwoba * a_traj_mult

        # 8. Defensa y Fatiga
        h_fatigue = self.loader.get_bullpen_fatigue(game['home_id'], game['date'])
        a_fatigue = self.loader.get_bullpen_fatigue(game['away_id'], game['date'])
        h_fielding = self.loader.get_team_fielding_speed(game['home_id'], current_year)
        a_fielding = self.loader.get_team_fielding_speed(game['away_id'], current_year)
        
        # 9. Generación de Lambda para Monte Carlo
        # INTERRUPTOR JETLAG: Si está apagado, pasamos None para que no encuentre viajes previos
        active_schedule = schedule_df if self.active_features.get('jetlag', True) else None

        h_power = self.engine.calculate_power_score(
            h_xwoba_adj, pf, league_avg_runs, game['home_id'], 
            game['date'], active_schedule, weather_data, game['venue_id']
        )
        a_power = self.engine.calculate_power_score(
            a_xwoba_adj, pf, league_avg_runs, game['away_id'], 
            game['date'], active_schedule, weather_data, game['venue_id']
        )
        
        h_def_ra9 = self.engine.calculate_defense_score(h_pstats, h_bullpen, h_fatigue, h_fielding)
        a_def_ra9 = self.engine.calculate_defense_score(a_pstats, a_bullpen, a_fatigue, a_fielding)

        # 10. Simulación Estocástica de Monte Carlo (V17.9 Dynamic HFA + K9 Volatilidad)
        
        hfa_dynamic = get_hfa_factor(game['venue_id']) 
        
        win_prob, h_runs, a_runs, _ = self.engine.run_monte_carlo_simulation(
            h_pow=h_power, 
            h_def=h_def_ra9, 
            a_pow=a_power, 
            a_def=a_def_ra9, 
            rounds=SIMULATION_ROUNDS, 
            league_avg_runs=league_avg_runs, 
            h_k9=h_k9,
            a_k9=a_k9,
            h_ip=h_ip, # <--- NUEVO
            a_ip=a_ip, # <--- NUEVO
            hfa=hfa_dynamic
        )

        # 11. Análisis de Sensibilidad (Stress Testing con K9 e IP incluidos)
        delta = 0.05
        prob_high, _, _, _ = self.engine.run_monte_carlo_simulation(
            h_power*(1+delta), h_def_ra9, a_power*(1-delta), a_def_ra9, 
            STRESS_TEST_ROUNDS, league_avg_runs, h_k9, a_k9, h_ip, a_ip, hfa_dynamic
        )
        prob_low, _, _, _ = self.engine.run_monte_carlo_simulation(
            h_power*(1-delta), h_def_ra9, a_power*(1+delta), a_def_ra9, 
            STRESS_TEST_ROUNDS, league_avg_runs, h_k9, a_k9, h_ip, a_ip, hfa_dynamic
        )

        input_sensitivity = abs(prob_high - prob_low) / 2
        
        # 12. Calibración Final (Temperature Scaling)
        is_calibrated = False
        if self.calibrator is not None and 'T' in self.calibrator:
            from scipy.special import logit, expit
            import numpy as np
            
            T = self.calibrator['T']
            
            # Clipping de seguridad
            clipped_home = np.clip(win_prob, 1e-6, 1 - 1e-6)
            clipped_away = np.clip(1.0 - win_prob, 1e-6, 1 - 1e-6)
            
            # Escalar
            home_prob_cal = float(expit(logit(clipped_home) / T))
            away_prob_cal = float(expit(logit(clipped_away) / T))
            
            # Re-normalizar a 1.0
            total_prob = home_prob_cal + away_prob_cal
            win_prob = home_prob_cal / total_prob
            is_calibrated = True

        winner = game['home_name'] if win_prob > 0.5 else game['away_name']

        return {
            'game': f"{game['away_name']} @ {game['home_name']}",
            'winner': winner,
            'home_prob': win_prob,
            'away_prob': 1.0 - win_prob,
            'confidence': win_prob if winner == game['home_name'] else 1.0 - win_prob,
            'score': {'home': h_runs, 'away': a_runs, 'total': h_runs + a_runs},
            'details': {
                'sensitivity': f"±{input_sensitivity*100:.1f}%",
                'pitching': f"H: {h_pstats['xera']:.2f} | A: {a_pstats['xera']:.2f}",
                'fatigue': f"H: {h_fatigue:.2f} | A: {a_fatigue:.2f}",
                'lineup': "CONFIRMADO"
            },
            'key_factor': "Señal Calibrada" if is_calibrated else "Ventaja Estructural",
            'raw_sensitivity': input_sensitivity
        }
    
    def get_todays_games(self):
        import datetime
        return self.loader.get_schedule(datetime.date.today().strftime("%Y-%m-%d"))