# xray_game.py - Escáner Forense de Predicciones
import sys
from model import MLBPredictor
from config import get_hfa_factor

def xray_specific_game(date_str, home_team_name):
    print(f"\n{'='*70}")
    print(f"🔬 INICIANDO RAYOS-X FORENSE: {home_team_name} el {date_str}")
    print(f"{'='*70}")
    
    predictor = MLBPredictor(use_calibrator=True)
    games = predictor.loader.get_schedule(date_str)
    
    target_game = None
    for g in games:
        if home_team_name.lower() in g['home_name'].lower() or home_team_name.lower() in g['away_name'].lower():
            target_game = g
            break
            
    if not target_game:
        print(f"❌ Juego no encontrado para {home_team_name} en la fecha {date_str}.")
        return
        
    print(f"\n⚾ PARTIDO: {target_game['away_name']} (Visita) vs {target_game['home_name']} (Local)")
    print(f"Estado Real: {target_game['status']} | Ganador Real: {target_game['real_winner']}")
    
    # ---------------------------------------------------------
    # 1. PITCHING Y DEFENSA
    # ---------------------------------------------------------
    h_pstats = predictor.loader.get_pitcher_xera_stats(target_game['home_pitcher'])
    a_pstats = predictor.loader.get_pitcher_xera_stats(target_game['away_pitcher'])
    h_hand = predictor.loader.get_pitcher_hand(target_game['home_pitcher'])
    a_hand = predictor.loader.get_pitcher_hand(target_game['away_pitcher'])
    
    h_bullpen = predictor.loader.get_bullpen_stats(target_game['home_id'], date_str)
    a_bullpen = predictor.loader.get_bullpen_stats(target_game['away_id'], date_str)
    
    print(f"\n[1] RADIOGRAFÍA DE PITCHING (Talento Puro de Prevención):")
    print(f"  ➤ Abridor Local (Lanza a la {h_hand}): xERA={h_pstats['xera']:.2f} | K/9={h_pstats['k9']:.1f} | IP Histórico={h_pstats['ip']:.1f}")
    print(f"  ➤ Abridor Visita (Lanza a la {a_hand}): xERA={a_pstats['xera']:.2f} | K/9={a_pstats['k9']:.1f} | IP Histórico={a_pstats['ip']:.1f}")
    print(f"  ➤ Bullpen Local (FIP): {h_bullpen['high_leverage_fip']:.2f}")
    print(f"  ➤ Bullpen Visita (FIP): {a_bullpen['high_leverage_fip']:.2f}")

    # ---------------------------------------------------------
    # 2. BATEO Y PLATOON SPLITS
    # ---------------------------------------------------------
    h_xwoba, _ = predictor.loader.get_confirmed_lineup_xwoba(target_game['id'], 'home', vs_hand=a_hand, use_hot_hand=False)
    a_xwoba, _ = predictor.loader.get_confirmed_lineup_xwoba(target_game['id'], 'away', vs_hand=h_hand, use_hot_hand=False)
    
    print(f"\n[2] RADIOGRAFÍA DE OFENSIVA (Talento al Bat):")
    print(f"  ➤ Lineup Local vs Pitcher {a_hand} (Visita): xwOBA = {h_xwoba:.4f}")
    print(f"  ➤ Lineup Visita vs Pitcher {h_hand} (Local): xwOBA = {a_xwoba:.4f}")

    # ---------------------------------------------------------
    # 3. FÍSICA Y ENTORNO
    # ---------------------------------------------------------
    pf = predictor.engine.get_park_factor(target_game['venue_id'])
    weather_data = predictor.loader.get_weather(target_game['venue_id'])
    w_mult = predictor.engine.calculate_weather_multiplier(target_game['venue_id'], weather_data)
    hfa = get_hfa_factor(target_game['venue_id'])
    
    print(f"\n[3] CONDICIONES FÍSICAS Y ESTADIO:")
    print(f"  ➤ Park Factor (Carreras Base): {pf:.3f}")
    print(f"  ➤ Multiplicador de Clima (Viento/Temp): {w_mult:.3f}")
    print(f"  ➤ Ventaja de Localía (HFA): {hfa:.3f}")

    # ---------------------------------------------------------
    # 4. CÁLCULO DE PODER FINAL (Antes de Simular)
    # ---------------------------------------------------------
    league_avg_runs = predictor.loader.get_league_run_environment(date_str)
    
    h_power = predictor.engine.calculate_power_score(h_xwoba, pf, league_avg_runs, target_game['home_id'], date_str, None, weather_data, target_game['venue_id'])
    a_power = predictor.engine.calculate_power_score(a_xwoba, pf, league_avg_runs, target_game['away_id'], date_str, None, weather_data, target_game['venue_id'])
    
    h_def_ra9 = predictor.engine.calculate_defense_score(h_pstats, h_bullpen, 0, 0.985)
    a_def_ra9 = predictor.engine.calculate_defense_score(a_pstats, a_bullpen, 0, 0.985)

    print(f"\n[4] MOTORES DE MONTE CARLO (Lambdas Base Generados):")
    print(f"  ➤ Local - Poder Ofensivo Generado: {h_power:.2f} | Prevención de Carreras (RA9): {h_def_ra9:.2f}")
    print(f"  ➤ Visita - Poder Ofensivo Generado: {a_power:.2f} | Prevención de Carreras (RA9): {a_def_ra9:.2f}")

    # ---------------------------------------------------------
    # 5. PREDICCIÓN FINAL DEL SISTEMA
    # ---------------------------------------------------------
    print(f"\n[5] RESOLUCIÓN DEL MODELO:")
    res = predictor.predict_game(target_game)
    if 'error' in res:
        print(f"  ❌ Error en predicción: {res['error']}")
    else:
        print(f"  ➤ Score Proyectado por Monte Carlo: {res['score']['away']} (Visita) - {res['score']['home']} (Local)")
        print(f"  ➤ Probabilidad FINAL Calibrada (Local): {res['home_prob']*100:.2f}%")
        print(f"  ➤ Sensibilidad al Estrés (K9/IP): {res['details']['sensitivity']}")
        
    print(f"{'='*70}\n")

if __name__ == "__main__":
    # INSTRUCCIONES: Cambia la fecha y el equipo por un partido real donde hayas perdido dinero.
    FECHA_DEL_JUEGO = "2024-06-02" 
    EQUIPO_LOCAL = "Mets" 
    
    xray_specific_game(FECHA_DEL_JUEGO, EQUIPO_LOCAL)