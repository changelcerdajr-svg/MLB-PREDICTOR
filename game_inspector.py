# game_inspector.py - Herramienta de Rayos X para Auditoria de Datos
from data_loader import MLBDataLoader
from features import FeatureEngine
from model import MLBPredictor
from datetime import datetime
import json

def inspect_todays_first_game():
    print("\n" + "="*70)
    print(" INICIANDO MODO RAYOS X (INSPECCION PROFUNDA DE EXTRACCION) ")
    print("="*70)

    # Inicializamos tus motores
    loader = MLBDataLoader()
    engine = FeatureEngine()
    predictor = MLBPredictor(use_calibrator=True)

    # 1. Obtener juegos de hoy
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"Buscando calendario para: {today_str}...\n")
    games = loader.get_schedule(today_str)

    if not games:
        print(f"[X] No hay juegos programados por la MLB para hoy ({today_str}).")
        print("Si quieres probar con una fecha pasada, cambia 'today_str' en el codigo.")
        return

    # Tomamos el primer juego de la lista para analizarlo a fondo
    game = games[0]
    
    print(f"[1] INFO DEL JUEGO")
    print(f"Partido: {game['away_name']} @ {game['home_name']}")
    print(f"Game ID: {game['id']} | Venue ID: {game['venue_id']}")

    # 2. Clima y Estadio
    print("\n[2] CLIMA Y ESTADIO")
    pf = engine.get_park_factor(game['venue_id'])
    weather = loader.get_weather(game['venue_id'])
    print(f"Park Factor Base: {pf}")
    print(f"Datos Meteorologicos: {json.dumps(weather, indent=2)}")
    print(f"Multiplicador Efectivo de Clima: {engine.calculate_weather_multiplier(game['venue_id'], weather):.4f}")

    # 3. Lanzadores Abridores
    print("\n[3] ABRIDORES (Talento, Suerte e Incertidumbre)")
    h_pstats = loader.get_pitcher_xera_stats(game['home_pitcher'])
    a_pstats = loader.get_pitcher_xera_stats(game['away_pitcher'])
    print(f"Local ({game['home_name']}):")
    print(f"  -> xERA: {h_pstats.get('xera', 4.0):.2f} | K/9: {h_pstats.get('k9', 9.0):.2f} | IP: {h_pstats.get('ip', 0):.1f} | BABIP: {h_pstats.get('babip', .300):.3f}")
    print(f"Visitante ({game['away_name']}):")
    print(f"  -> xERA: {a_pstats.get('xera', 4.0):.2f} | K/9: {a_pstats.get('k9', 9.0):.2f} | IP: {a_pstats.get('ip', 0):.1f} | BABIP: {a_pstats.get('babip', .300):.3f}")

    # 4. Bullpen y Fatiga
    print("\n[4] BULLPEN Y FATIGA")
    h_bullpen = loader.get_bullpen_stats(game['home_id'])
    a_bullpen = loader.get_bullpen_stats(game['away_id'])
    h_fatigue = loader.get_bullpen_fatigue(game['home_id'], game['date'])
    a_fatigue = loader.get_bullpen_fatigue(game['away_id'], game['date'])
    
    print(f"Local:")
    print(f"  -> FIP Global: {h_bullpen.get('fip', 4.10):.2f} | FIP Alta Palanca: {h_bullpen.get('high_leverage_fip', 4.10):.2f} | Penalizacion Fatiga: +{h_fatigue:.2f} runs")
    print(f"Visitante:")
    print(f"  -> FIP Global: {a_bullpen.get('fip', 4.10):.2f} | FIP Alta Palanca: {a_bullpen.get('high_leverage_fip', 4.10):.2f} | Penalizacion Fatiga: +{a_fatigue:.2f} runs")

    # 5. Lineups y Platoon (xwOBA)
    print("\n[5] LINEUPS CONFIRMADOS (Poder Ofensivo)")
    h_hand = loader.get_pitcher_hand(game['home_pitcher'])
    a_hand = loader.get_pitcher_hand(game['away_pitcher'])

    print(f"Mano del abridor local: {h_hand} | Mano del abridor visitante: {a_hand}")
    
    h_xwoba, h_conf = loader.get_confirmed_lineup_xwoba(game['id'], 'home', a_hand, game['home_id'])
    a_xwoba, a_conf = loader.get_confirmed_lineup_xwoba(game['id'], 'away', h_hand, game['away_id'])
    
    print(f"Local xwOBA (vs {a_hand}): {h_xwoba} | Status: {'Confirmado' if h_conf else 'Esperando a la MLB'}")
    print(f"Visitante xwOBA (vs {h_hand}): {a_xwoba} | Status: {'Confirmado' if a_conf else 'Esperando a la MLB'}")

    # 6. Variables Perifericas (Defensa y Disciplina)
    print("\n[6] PERIFERICOS (Disciplina en el plato y Balistica)")
    h_disc = loader.get_team_discipline(game['home_id'])
    a_disc = loader.get_team_discipline(game['away_id'])
    h_goao = loader.get_batted_ball_profile(game['home_id'])
    a_goao = loader.get_batted_ball_profile(game['away_id'])
    
    print(f"Local     - K%: {h_disc*100:.1f}% | GroundOut/AirOut Ratio: {h_goao:.2f}")
    print(f"Visitante - K%: {a_disc*100:.1f}% | GroundOut/AirOut Ratio: {a_goao:.2f}")

    # 7. Ejecutar motor estocastico completo
    print("\n[7] RESULTADO FINAL DEL MODELO (Salida de predict_game)")
    if not h_conf or not a_conf:
        print("[!] No se puede correr la simulacion final porque faltan lineups oficiales.")
    else:
        resultado = predictor.predict_game(game)
        print(json.dumps(resultado, indent=2))
        
    print("\n" + "="*70)
    print(" FIN DE LA INSPECCION ")
    print("="*70)

if __name__ == "__main__":
    inspect_todays_first_game()