# model.py
# Orquestador V17.9 (Motor Statcast Total + Volatilidad K/9)
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
        # 1. Preparación de Entorno
        schedule_df = self.loader.get_travel_schedule_window(game['date'], days_back=2)
        league_avg_runs = self.loader.get_league_run_environment(game['date'])
        
        # 2. Pitcheo con xERA y Mano del Lanzador
        # 2. Pitcheo con xERA, K/9 e IP para Incertidumbre (V18.0)
        h_pstats = self.loader.get_pitcher_xera_stats(game['home_pitcher'])
        a_pstats = self.loader.get_pitcher_xera_stats(game['away_pitcher'])
        
        h_k9 = h_pstats.get('k9', 9.0)
        a_k9 = a_pstats.get('k9', 9.0)
        h_ip = h_pstats.get('ip', 0.0)  # <--- NUEVO
        a_ip = a_pstats.get('ip', 0.0)  # <--- NUEVO
        
        h_hand = self.loader.get_pitcher_hand(game['home_pitcher'])
        a_hand = self.loader.get_pitcher_hand(game['away_pitcher'])
        
        h_bullpen = self.loader.get_bullpen_stats(game['home_id'])
        a_bullpen = self.loader.get_bullpen_stats(game['away_id'])

        # 3. Lineups con xwOBA Real (Platoon Proxy V17.9)
        h_xwoba, h_confirmed = self.loader.get_confirmed_lineup_xwoba(game['id'], 'home', vs_hand=a_hand, team_id=game['home_id'])
        a_xwoba, a_confirmed = self.loader.get_confirmed_lineup_xwoba(game['id'], 'away', vs_hand=h_hand, team_id=game['away_id'])

        if not h_confirmed or not a_confirmed:
            return {'error': 'Lineups no confirmados. Operación bloqueada.'}

        # 4. Señal Real (Sin Ponderaciones Antiguas)
        h_xwoba_adj = h_xwoba 
        a_xwoba_adj = a_xwoba

        # --- REESTRUCTURACIÓN M4 ---
        # 5a. Obtenemos el Park Factor primero para usarlo en la balística
        pf = self.engine.get_park_factor(game['venue_id'])
        weather_data = self.loader.get_weather(game['venue_id'])

        # 5b. Ajustes Biomecánicos y Balísticos (Contextualizados al Estadio)
        h_pitcher_goao = self.loader.get_batted_ball_profile(game['home_pitcher'], is_pitcher=True)
        a_pitcher_goao = self.loader.get_batted_ball_profile(game['away_pitcher'], is_pitcher=True)
        h_team_goao = self.loader.get_batted_ball_profile(game['home_id'], is_pitcher=False)
        a_team_goao = self.loader.get_batted_ball_profile(game['away_id'], is_pitcher=False)

        def calculate_trajectory_multiplier(pitcher_goao, team_goao, park_factor):
            # M4: Si el parque favorece el bateo (pf > 1), los Fly Balls (GO/AO bajo) son más peligrosos
            diff = (team_goao - pitcher_goao)
            
            # Ajustamos el impacto basándonos en si el estadio ayuda o perjudica
            park_adjustment = (park_factor - 1.0) 
            
            # La interacción ahora suma el contexto del parque
            multiplier = 1.0 + (diff * 0.05) + (diff * park_adjustment * 0.1)
            return max(0.92, min(1.08, multiplier))

        # El equipo local batea contra el pitcher visitante en su propio parque
        h_xwoba_adj *= calculate_trajectory_multiplier(a_pitcher_goao, h_team_goao, pf)
        # El equipo visitante batea contra el pitcher local en el mismo parque
        a_xwoba_adj *= calculate_trajectory_multiplier(h_pitcher_goao, a_team_goao, pf)

        # 6. Arsenal Advantage
        h_discipline_k_rate = self.loader.get_team_discipline(game['home_id'])
        a_discipline_k_rate = self.loader.get_team_discipline(game['away_id'])

        def calculate_arsenal_advantage(pitcher_k9, batter_k_rate):
            k9_diff = (pitcher_k9 - 8.5) / 8.5
            k_rate_diff = (batter_k_rate - 0.22) / 0.22
            
            # Sumamos las ventajas direccionales
            pitcher_edge = k9_diff + k_rate_diff
            
            # Coeficiente ajustado de 0.15 a 0.08 para evitar saturar el clamp
            multiplier = 1.0 - (pitcher_edge * 0.08)
            
            return max(0.90, min(1.10, multiplier))
        
        h_xwoba_adj *= calculate_arsenal_advantage(a_pstats['k9'], h_discipline_k_rate)
        a_xwoba_adj *= calculate_arsenal_advantage(h_pstats['k9'], a_discipline_k_rate)

        # 7. Momentum
        h_mom = self.loader.get_team_momentum(game['home_id'], game['date'])
        a_mom = self.loader.get_team_momentum(game['away_id'], game['date'])
        
        h_streak_mult = 1.0 + max(-0.03, min(0.03, h_mom['streak'] * 0.005))
        a_streak_mult = 1.0 + max(-0.03, min(0.03, a_mom['streak'] * 0.005))

        # 8. Defensa y Fatiga (El clima y PF ya se calcularon en el 5a)
        h_fatigue = self.loader.get_bullpen_fatigue(game['home_id'], game['date'])
        a_fatigue = self.loader.get_bullpen_fatigue(game['away_id'], game['date'])
        h_fielding = self.loader.get_team_fielding_speed(game['home_id'])
        a_fielding = self.loader.get_team_fielding_speed(game['away_id'])
        # ----------------------------------------
        
      
        # 9. Generación de Lambda para Monte Carlo
        h_power = self.engine.calculate_power_score(h_xwoba_adj, pf, league_avg_runs, game['home_id'], game['date'], schedule_df, weather_data, game['venue_id']) * h_streak_mult
        a_power = self.engine.calculate_power_score(a_xwoba_adj, pf, league_avg_runs, game['away_id'], game['date'], schedule_df, weather_data, game['venue_id']) * a_streak_mult
        
        h_def_ra9 = self.engine.calculate_defense_score(h_pstats, h_bullpen, h_fatigue, h_fielding) / h_streak_mult
        a_def_ra9 = self.engine.calculate_defense_score(a_pstats, a_bullpen, a_fatigue, a_fielding) / a_streak_mult

        # 10. Simulación Estocástica de Monte Carlo (V17.9 Dynamic HFA + K9 Volatilidad)
        from config import get_hfa_factor
        hfa_dynamic = get_hfa_factor(game['venue_id']) 
        
        win_prob, h_runs, a_runs, _ = self.engine.run_monte_carlo_simulation(
            h_pow=h_power, 
            h_def=h_def_ra9, 
            a_pow=a_power, 
            a_def=a_def_ra9, 
            rounds=SIMULATION_ROUNDS, 
            league_avg_runs=league_avg_runs, 
            pf=pf,
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
            STRESS_TEST_ROUNDS, league_avg_runs, pf, h_k9, a_k9, h_ip, a_ip, hfa_dynamic
        )
        prob_low, _, _, _ = self.engine.run_monte_carlo_simulation(
            h_power*(1-delta), h_def_ra9, a_power*(1+delta), a_def_ra9, 
            STRESS_TEST_ROUNDS, league_avg_runs, pf, h_k9, a_k9, h_ip, a_ip, hfa_dynamic
        )
        input_sensitivity = abs(prob_high - prob_low) / 2
        
        # 12. Calibración Final
        is_calibrated = False
        if self.calibrator is not None:
            win_prob = float(self.calibrator.predict([win_prob])[0])
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