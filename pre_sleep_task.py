import subprocess
import time
import datetime

def log_error(script_name, error_msg):
    """Guarda los errores en un archivo para revisión matutina."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("log_noche.txt", "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] ERROR en {script_name}: {error_msg}\n")

def run_script_blindado(command):
    """Ejecuta un script y, si falla, registra el error pero permite continuar."""
    print(f"\n🚀 Iniciando: {command}...")
    try:
        # Ejecutamos el comando. shell=True es necesario en Windows.
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"⚠️ {command} terminó con advertencias (Código {result.returncode}).")
            log_error(command, result.stderr)
        else:
            print(f"✅ {command} completado con éxito.")
            
    except Exception as e:
        print(f"❌ Fallo crítico al intentar lanzar {command}.")
        log_error(command, str(e))

if __name__ == "__main__":
    print("="*50)
    print("🌙 RUTINA NOCTURNA MLB PREDICTOR V19.1 - MODO RESILIENTE")
    print("="*50)
    
    # 1. SCRAPER: Aunque falle (ej. VegasInsider caído), queremos que lo demás corra
    run_script_blindado("python live_odds_scraper.py")
    
    # Pausa de seguridad para que el sistema libere archivos
    time.sleep(2)
    
    # 2. CALIBRACIÓN: Si falla, usaremos el .pkl anterior (no es el fin del mundo)
    run_script_blindado("python train_calibration.py")
    
    time.sleep(2)
    
    # 3. VALIDACIÓN OOS: Revisión final de salud
    run_script_blindado("python oos_validation.py")
    
    # 4. GIT PUSH: Sube lo que se haya logrado procesar
    print("\n📦 Sincronizando con GitHub...")
    run_script_blindado("git add .")
    run_script_blindado('git commit -m "Auto-update: Routine night sync"')
    run_script_blindado("git push")

    print("\n" + "="*50)
    print("✨ PROCESO FINALIZADO.")
    print("Revisa 'log_noche.txt' mañana para ver si hubo contratiempos.")
    print("="*50)