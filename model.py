# model.py
# Orquestador V11.5 (Institucional - Purificado)
import pickle
import os
from data_loader import MLBDataLoader
from features import FeatureEngine
from umpire import UmpireEngine
from config import SIMULATION_ROUNDS

class MLBPredictor:
    def __init__(self, use_calibrator=True):
        self.loader = MLBDataLoader()
        self.engine = FeatureEngine()
        self.umpire = UmpireEngine()
        
        self.calibrator = None
        if use_calibrator:
            try:
                if os.path.exists('isotonic_calibrator.pkl'):
                    with open('isotonic_calibrator.pkl', 'rb') as f:
                        self.calibrator = pickle.load(f)
                else:
                    print("Calibrador no encontrado. Intentando entrenar uno nuevo...")
                    from train_calibration import train_isotonic_calibrator
                    train_isotonic_calibrator() # Esto genera el .pkl en el servidor
                    with open('isotonic_calibrator.pkl', 'rb') as f:
                        self.calibrator = pickle.load(f)
            except Exception as e:
                print(f"Error de compatibilidad de Pickle: {e}. El modelo correrá sin calibración.")
                self.calibrator = None

    def predict_game(self, game):
        # 0. Datos Generales (Calendario Rodante)
        schedule_df = self.loader.get_travel_schedule_window(game['date'], days_back=2)

        # 1. Contexto de Liga
        league_avg_runs = self.loader.get_league_run_environment(game['date'])
        
        # 2. Pitcheo
        h_pstats = self.loader.get_pitcher_fip_stats(game['home_pitcher'])
        a_pstats = self.loader.get_pitcher_fip_stats(game['away_pitcher'])
        h_bullpen = self.loader.get_bullpen_stats(game['home_id'])
        a_bullpen = self.loader.get_bullpen_stats(game['away_id'])

        # 3. Lineups
        h_ops, h_confirmed = self.loader.get_confirmed_lineup_ops(game['id'], 'home')
        a_ops, a_confirmed = self.loader.get_confirmed_lineup_ops(game['id'], 'away')
        
        # --- COMPUERTAS DE SEGURIDAD ESTRICTAS ---
        if abs(h_pstats['fip'] - 4.30) < 0.001 or abs(a_pstats['fip'] - 4.30) < 0.001:
            return {'error': 'Datos de pitcheo insuficientes o Opener detectado. Simulación abortada.'}
            
        if not h_confirmed or not a_confirmed:
            return {'error': 'Lineups no confirmados. Simulación abortada para evitar sesgos de equipo.'}

        # 4. Fatiga
        h_fatigue = self.loader.get_bullpen_fatigue(game['home_id'], game['date'])
        a_fatigue = self.loader.get_bullpen_fatigue(game['away_id'], game['date'])

        # 5. Variables Secundarias
        h_smallball = self.loader.get_team_fielding_speed(game['home_id'])
        a_smallball = self.loader.get_team_fielding_speed(game['away_id'])
        
        ump_data = self.umpire.get_game_umpire()
        weather = self.loader.get_weather(game['venue_id'])
        pf = self.engine.get_park_factor(game['venue_id'])
        
        temp = weather.get('temperature', 21)
        wind = weather.get('windspeed', 5)

        # 6. Cálculo de Scores
        h_power = self.engine.calculate_power_score(
            h_ops, pf, temp, wind, ump_data.get('factor', 1.0), h_smallball, league_avg_runs,
            game['home_id'], game['date'], schedule_df 
        )
        a_power = self.engine.calculate_power_score(
            a_ops, pf, temp, wind, ump_data.get('factor', 1.0), a_smallball, league_avg_runs,
            game['away_id'], game['date'], schedule_df 
        )
        
        h_def = self.engine.calculate_defense_score(h_pstats, h_bullpen, h_fatigue, ump_data.get('factor', 1.0), h_smallball)
        a_def = self.engine.calculate_defense_score(a_pstats, a_bullpen, a_fatigue, ump_data.get('factor', 1.0), a_smallball)

        # 7. Simulación Estocástica
        win_prob, h_runs, a_runs, uncertainty = self.engine.run_monte_carlo_simulation(
            h_power, h_def, a_power, a_def, rounds=SIMULATION_ROUNDS, league_avg_runs=league_avg_runs, pf=pf
        )
        
        # 8. Calibración Empírica
        is_calibrated = False
        if self.calibrator is not None:
            win_prob = float(self.calibrator.predict([win_prob])[0])
            is_calibrated = True

        home_win_prob = win_prob
        away_win_prob = 1.0 - win_prob
        winner = game['home_name'] if win_prob > 0.5 else game['away_name']
        confidence = home_win_prob if winner == game['home_name'] else away_win_prob

        # 9. Factor Clave (Lógica de reporte)
        if uncertainty > 0.035:
            key = "ALTA VOLATILIDAD / RIESGO"
        elif h_fatigue > 0.25 or a_fatigue > 0.25:
            key = "Fatiga de Bullpen Detectada"
        elif is_calibrated:
            key = "Señal Calibrada Empíricamente"
        else:
            key = "Ventaja Estructural Cruda"

        return {
            'game': f"{game['away_name']} @ {game['home_name']}",
            'winner': winner,
            'home_prob': home_win_prob,
            'away_prob': away_win_prob,
            'confidence': confidence,
            'score': {'home': h_runs, 'away': a_runs, 'total': h_runs + a_runs},
            'details': {
                'uncertainty': f"±{uncertainty*100:.2f}%",
                'pitching': f"H: FIP {h_pstats['fip']:.2f} | A: FIP {a_pstats['fip']:.2f}",
                'fatigue': f"H: {h_fatigue:.2f} | A: {a_fatigue:.2f}",
                'league_env': f"{league_avg_runs:.2f} R/G",
                'lineup': "PRO" if (h_confirmed and a_confirmed) else "AVG"
            },
            'key_factor': key
        }
    
    def get_todays_games(self):
        return self.loader.get_schedule()