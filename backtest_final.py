# backtest_final.py
# Auditoría Histórica Final V16.2 (OUT-OF-SAMPLE REAL)

from model import MLBPredictor
from datetime import datetime, timedelta

def run_out_of_sample_backtest():
    print("="*60)
    print(" 🔬 INICIANDO BACKTEST OUT-OF-SAMPLE V16.2")
    print("    (Totalmente desvinculado de la ventana de calibración)")
    print("="*60)
    
    # Ventana de Verano: Julio a Agosto 2024 (Evitando el overfit de Abril/Mayo)
    START_DATE = "2024-07-01"
    END_DATE = "2024-08-31" 
    
    # Apagamos el calibrador para evaluar el poder crudo del chasis
    predictor = MLBPredictor(use_calibrator=False) 
    predictor.loader._force_historical_mode = True 
    
    current_date = datetime.strptime(START_DATE, "%Y-%m-%d")
    end_date = datetime.strptime(END_DATE, "%Y-%m-%d")
    
    total_games = 0
    actionable_games = 0
    wins = 0
    home_wins = 0
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        games = predictor.loader.get_schedule(date_str)
        
        if not games:
            current_date += timedelta(days=1)
            continue
            
        print(f"📅 {date_str} [{len(games)} juegos]...", end=" ")
        
        for game in games:
            if game['status'] not in ['Final', 'Game Over', 'Completed', 'F']:
                continue
            try:
                h_score = game['real_score']['home']
                a_score = game['real_score']['away']
                if h_score == a_score: continue
                
                real_winner = game['home_name'] if h_score > a_score else game['away_name']
                
                res = predictor.predict_game(game)
                if 'error' in res: continue
                
                total_games += 1
                if real_winner == game['home_name']:
                    home_wins += 1
                    
                if res['confidence'] >= 0.55:
                    actionable_games += 1
                    if res['winner'] == real_winner:
                        wins += 1
            except Exception: pass
            
        print("OK")
        current_date += timedelta(days=1)
        
    print("\n" + "="*60)
    print(" 📊 RESULTADOS DEL BACKTEST OUT-OF-SAMPLE (Julio-Agosto 2024)")
    print("="*60)
    print(f"Juegos Totales Evaluados: {total_games}")
    
    if actionable_games > 0:
        accuracy = wins / actionable_games
        baseline = home_wins / total_games
        lift = accuracy - baseline
        
        print(f"💰 JUEGOS OPERADOS (Confianza > 55%): {actionable_games}")
        print(f"🎯 ACCURACY EN APUESTAS: {accuracy*100:.2f}% ({wins}/{actionable_games})")
        print(f"🏠 BASELINE DEL MERCADO: {baseline*100:.2f}%")
        
        if lift > 0:
            print(f"🚀 LIFT REAL DEL MODELO: +{lift*100:.2f}% (Señal Alpha Detectada)")
        else:
            print(f"⚠️ LIFT NEGATIVO: {lift*100:.2f}% (Ruido en el modelo)")
    else:
        print("No hubo juegos que superaran el umbral.")
    print("="*60)

if __name__ == "__main__":
    run_out_of_sample_backtest()