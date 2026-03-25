# main.py
# Interfaz de Usuario V10.4 (Interactive Uncertainty & Fatigue Edition)

import sys
from datetime import datetime
from model import MLBPredictor

def main():
    print("\n" + "⚾ "*25)
    print("   MLB PREDICTOR PRO - V10.4 (BAYESIAN + FATIGUE ENGINE)")
    print("   Power: NegBinomial + Regresión Lineups + Incertidumbre")
    print(f"   Fecha del Sistema: {datetime.now().strftime('%Y-%m-%d')}")
    print("⚾ "*25 + "\n")

    # 1. Inicializar el Cerebro
    print("🧠 Cargando motor V10.4 y consultando APIs...")
    predictor = MLBPredictor()

    # 2. Obtener Juegos
    try:
        games = predictor.get_todays_games()
    except Exception as e:
        print(f"❌ Error al conectar con la API: {e}")
        return

    if not games:
        print("⚠️ No hay juegos programados para la fecha configurada.")
        return

    # 3. Menú Interactivo
    while True:
        print(f"\n📡 Juegos Encontrados: {len(games)}")
        print(" ID  | VISITANTE              vs  LOCAL")
        print("-" * 50)
        
        # Filtramos para mostrar solo juegos pendientes o en curso para la lista
        for i, g in enumerate(games):
            status = g.get('status', 'Unknown')
            print(f" {i:<3} | {g['away_name']:<18} vs  {g['home_name']:<18} [{status}]")
        
        print("-" * 50)
        selection = input("\n🎲 Escribe el ID del juego a predecir (o 'q' para salir): ")
        
        if selection.lower() == 'q':
            print("👋 ¡Suerte en las apuestas!")
            break
        
        try:
            idx = int(selection)
            if 0 <= idx < len(games):
                selected_game = games[idx]
                
                print(f"\n🔄 Analizando {selected_game['away_name']} @ {selected_game['home_name']}...")
                print("   ↳ Revisando fatiga de bullpen (3 días)...")
                print("   ↳ Aplicando pesos de regresión...")
                print("   ↳ Simulando 10,000 escenarios (NegBinomial)...")
                
                # --- EJECUTAR PREDICCIÓN V10.4 ---
                res = predictor.predict_game(selected_game)
                
                # Extracción de variables para facilitar lectura
                det = res['details']
                conf_pct = res['confidence'] * 100
                
                # Lógica de Semáforo para Iconos
                icon = "🔴"
                if conf_pct > 60: icon = "🟢"
                elif conf_pct > 53: icon = "🟡"
                
                # Si hay alerta de volatilidad, el icono cambia a Warning
                if "RIESGO" in res['key_factor'] or "VOLATILIDAD" in res['key_factor']:
                    icon = "⚠️"

                # --- MOSTRAR RESULTADO ---
                print("\n" + "█"*65)
                print(f" 🏟️  {res['game'].upper()}")
                print("-" * 65)
                print(f" 🏆 GANADOR:       [{res['winner'].upper()}] {icon}")
                print(f" 📊 CONFIANZA:     {conf_pct:.1f}%")
                print(f" 🎲 INCERTIDUMBRE: {det.get('uncertainty', 'N/A')} (Desviación Estándar)")
                print(f" 🔑 FACTOR CLAVE:  {res['key_factor']}")
                print("-" * 65)
                print(f" 🔢 SCORE ESTIMADO: Visita {res['score']['away']:.1f} - Local {res['score']['home']:.1f}")
                print(f" ☁️  TOTAL PROYEC.: {res['score']['total']:.1f}")
                print("-" * 65)
                
                # DATOS AVANZADOS (V10.4)
                print(f" 📉 FATIGA BULLPEN: {det['fatigue']} (0.0 = Fresco, >0.25 = Cansado)")
                print(f" ⚾ PITCHING (FIP): {det['pitching']}")
                print(f" 📝 LINEUPS:        {det['lineup']} (Pesos de Regresión aplicados)")
                print(f" 🌍 ENTORNO LIGA:   {det['league_env']}")
                print("█"*65 + "\n")
                
                input("Presiona ENTER para continuar...")
            else:
                print("❌ ID fuera de rango. Intenta de nuevo.")
        except ValueError:
            print("❌ Por favor ingresa un número válido.")
        except Exception as e:
            print(f"❌ Error inesperado procesando el juego: {e}")

if __name__ == "__main__":
    main()