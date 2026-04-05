import cProfile
import pstats
import datetime
from model import MLBPredictor #

def encontrar_cuello_de_botella_multidia():
    print("Inicializando modelo...")
    # Apagamos el calibrador para la prueba pura de velocidad
    predictor = MLBPredictor(use_calibrator=False, use_hot_hand=True) 

    # 1. Configuración del viaje en el tiempo
    fecha_texto = "2024-04-01" # Día de inicio
    dias_a_simular = 3 # <--- AQUÍ LE MUEVES PARA VER MÁS DÍAS
    
    fecha_inicio = datetime.datetime.strptime(fecha_texto, "%Y-%m-%d")

    print(f"\nAnalizando {dias_a_simular} días consecutivos a partir del {fecha_texto}...")
    print("Presta atención a cómo la velocidad cambia del Día 1 a los siguientes.\n")

    # 2. Encendemos la radiografía
    profiler = cProfile.Profile()
    profiler.enable()
    
    # 3. Bucle Multi-Día
    for i in range(dias_a_simular):
        fecha_actual = (fecha_inicio + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        print(f"\n[DÍA {i+1}/{dias_a_simular}] --- {fecha_actual} ---")
        
        # Obtenemos los juegos de esa fecha específica
        games = predictor.loader.get_schedule(fecha_actual)
        
        if not games:
            print("  Sin juegos programados para hoy.")
            continue
            
        # Simulamos todos los juegos del día
        for juego in games:
            print(f"  -> Simulando: {juego['away_name']} @ {juego['home_name']}")
            predictor.predict_game(juego) #
            
    # 4. Apagamos la radiografía
    profiler.disable()

    # 5. Imprimimos el reporte
    stats = pstats.Stats(profiler)
    stats.sort_stats('tottime')
    
    print("\n=== TOP 15 FUNCIONES MÁS LENTAS (MULTI-DÍA) ===")
    stats.print_stats(15)

if __name__ == "__main__":
    encontrar_cuello_de_botella_multidia()