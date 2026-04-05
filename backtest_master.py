# backtest_master.py
# Motor de Validación Institucional V17.9 (Vig-Killer + Alpha True)

import json
import datetime
import textwrap
import numpy as np
from model import MLBPredictor
from financial import get_fair_prob, calculate_edge, american_to_prob, calculate_kelly
from hot_hand_updater import update_hot_hand_database
from config import CONFIDENCE_THRESHOLD, MAX_ODDS_LIMIT, KELLY_FRACTION, MAX_SENSITIVITY
from sklearn.metrics import brier_score_loss, log_loss
from config import USE_HOT_HAND_GLOBAL
from sklearn.metrics import log_loss, brier_score_loss

DATASET_PATH = 'data_odds/mlb_odds_dataset.json'
STARTING_BANKROLL = 10000.0   

def load_odds_data():
    try:
        with open(DATASET_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error cargando dataset de momios: {e}")
        return {}

def american_to_decimal(american):
    if american > 0: return (american / 100) + 1
    return (100 / abs(american)) + 1

def calculate_payout_flat(odds, stake=1.0):
    if odds > 0: return stake * (odds / 100)
    return stake * (100 / abs(odds))

def get_real_odds(odds_data, date_str, mlb_home_name):
    day_games = odds_data.get(date_str, [])
    if not day_games: return None, None
    mlb_clean = mlb_home_name.lower().strip()
    for game in day_games:
        dk_name = game.get('gameView', {}).get('homeTeam', {}).get('fullName', '').lower().strip()
        if mlb_clean in dk_name or dk_name in mlb_clean:
            ml_list = game.get('odds', {}).get('moneyline', [])
            for book in ml_list:
                if book.get('sportsbook') == 'draftkings':
                    line = book.get('currentLine')
                    if line: return line.get('homeOdds'), line.get('awayOdds')
    return None, None

def run_master_backtest(start_date_str, days=45, use_hot_hand=False, experiments=None):
    # Asegúrate de pasar 'experiments' al constructor del predictor
    predictor = MLBPredictor(use_calibrator=True, use_hot_hand=use_hot_hand, experiments=experiments)
    odds_data = load_odds_data()
    start_dt = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
    
    bankroll = STARTING_BANKROLL
    stats = {
        'total_games': 0, 'bets': 0, 'won': 0, 
        'flat_profit': 0.0, 'baseline_home_wins': 0,
        'total_real_edge': 0.0,
        'gross_won': 0.0,  # <--- NUEVO: Rastreará dólares ganados
        'gross_lost': 0.0  # <--- NUEVO: Rastreará dólares perdidos
    }
    
    # --- VECTORES CIENTÍFICOS (Para Grid Search / Brier Score) ---
    # --- VECTORES CIENTÍFICOS ---
    y_true = []
    y_prob = []
    
    # NUEVO: Vectores exclusivos para las apuestas realizadas
    bet_y_true = []
    bet_y_prob = []
    
    peak_bankroll = STARTING_BANKROLL
    recent_edges = []
    recent_results = []
    recent_expected = []

    print("=" * 70)
    print(f"🚀 INICIANDO BACKTEST MASTER V17.9: {start_date_str} (+{days} días)")
    print(f"Lógica: Vig-Killer Activo | Talento Calibrado (0.885) | Alpha Real")
    print("=" * 70)
    
    for i in range(days):
        date_str = (start_dt + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        
        if use_hot_hand:
            # Actualización de Capa 2 para el día simulado
            success = update_hot_hand_database(target_date_str=date_str)
            if success:
                predictor.loader.reload_hot_hand()

        games = predictor.loader.get_schedule(date_str)
        
        for g in games:
            if g['status'] != 'Final' or g['real_winner'] is None: continue
            
            stats['total_games'] += 1
            if g['real_winner'] == g['home_name']: stats['baseline_home_wins'] += 1
                
            h_odds, a_odds = get_real_odds(odds_data, date_str, g['home_name'])
            if h_odds is None or a_odds is None: continue
            
            res = predictor.predict_game(g)
            if 'error' in res: continue
            
            # --- RECOLECCIÓN DE DATOS PARA GRID SEARCH ---
            prob = res['confidence']
            pick, winner = res['winner'], g['real_winner']
            home_prob = res['home_prob']
            
            # FIX CRÍTICO 3: Recolectar TODOS los juegos para un Brier Score honesto en el Grid Search
            y_prob.append(home_prob)
            y_true.append(1 if winner == g['home_name'] else 0)

            # --- FILTROS DE AUDITORÍA OPERATIVA ---
            if prob < CONFIDENCE_THRESHOLD: continue

            sensitivity = res.get('raw_sensitivity', 1.0)
            if sensitivity > MAX_SENSITIVITY: continue

            curr_odds = h_odds if pick == g['home_name'] else a_odds
            if curr_odds < MAX_ODDS_LIMIT: continue

            fair_h, fair_a = get_fair_prob(h_odds, a_odds)
            market_prob_clean = fair_h if pick == g['home_name'] else fair_a
            
            edge_report = calculate_edge(prob, market_prob_clean)
            real_edge = edge_report['edge']
            
            if real_edge <= 0.015: continue

            # --- GESTIÓN FINANCIERA ---
            # --- GESTIÓN FINANCIERA (Freno de Emergencia Real) ---
            if bankroll > peak_bankroll: peak_bankroll = bankroll
            
            current_drawdown = (peak_bankroll - bankroll) / peak_bankroll
            
            # HARD STOP: Si pierdes el 20% del máximo histórico, el bot deja de operar.
            if current_drawdown >= 0.20:
                print(f"\n[🛑 HALT] Drawdown del {current_drawdown*100:.1f}%. Riesgo inaceptable. Sistema detenido.")
                break 
                
            # Kelly Dinámico (Protección contra Varianza)
            current_fraction = KELLY_FRACTION
            
            if current_drawdown >= 0.15:
                # SOFT STOP: Si pierdes el 15%, cortamos el riesgo al 25% de lo normal.
                current_fraction = KELLY_FRACTION * 0.25 
                print(f" [⚠️ ALERTA] Drawdown {current_drawdown*100:.1f}%. Reduciendo a 1/4 Kelly.")
            elif len(recent_results) == 30:
                actual_wr = sum(recent_results) / 30.0
                expected_wr = sum(recent_expected) / 30.0
                
                if actual_wr < expected_wr - 0.05: 
                    # Sub-ejecución (Frío): Protección simétrica
                    current_fraction = KELLY_FRACTION * 0.5
                elif actual_wr > expected_wr + 0.05: 
                    # Sobre-ejecución (Caliente): En lugar de 1.0 (muy arriesgado), limitamos a 0.75
                    current_fraction = KELLY_FRACTION * 0.75
            
            stake_pct = calculate_kelly(prob, curr_odds, fraction=current_fraction)
            if stake_pct <= 0: continue
            
            # --- NUEVO: Registrar la probabilidad y resultado SOLO para apuestas reales ---
            bet_y_true.append(1 if pick == winner else 0)
            bet_y_prob.append(prob)
            
            stake_units = bankroll * stake_pct
            stats['bets'] += 1
            stats['total_real_edge'] += real_edge
            
            if pick == winner:
                stats['won'] += 1
                stats['flat_profit'] += calculate_payout_flat(curr_odds)
                gain = stake_units * (american_to_decimal(curr_odds) - 1)
                bankroll += gain
                stats['gross_won'] += gain # <--- REGISTRO BRUTO
                print(f"✅ {date_str} | {pick:15} | Edge: {real_edge*100:+.1f}% | +${gain:.2f}")
            else:
                stats['flat_profit'] -= 1.0
                bankroll -= stake_units
                stats['gross_lost'] += stake_units # <--- REGISTRO BRUTO
                print(f"❌ {date_str} | {pick:15} | Edge: {real_edge*100:+.1f}% | -${stake_units:.2f}")

            recent_results.append(1 if pick == winner else 0)
            recent_expected.append(prob)
            if len(recent_results) > 30:
                recent_results.pop(0)
                recent_expected.pop(0)

    # --- REPORTE FINAL COMPLETO ---
    print("\n" + "=" * 70)
    print("📊 REPORTE DE AUDITORÍA CIENTÍFICA V17.9")
    print("=" * 70)
    
    if stats['bets'] > 0:
        win_rate = (stats['won'] / stats['bets']) * 100
        roi = (stats['flat_profit'] / stats['bets']) * 100
        avg_edge = (stats['total_real_edge'] / stats['bets']) * 100
        
        brier = brier_score_loss(y_true, y_prob)
        logloss = log_loss(y_true, y_prob)
        sharpness = np.std(y_prob)
        
        print(f"Muestra Global:       {stats['total_games']} juegos evaluados")
        print(f"Calibración Global:   Brier={brier:.4f} | Log Loss={logloss:.4f} | Sharpness={sharpness:.3f}")
        print("-" * 70)
        
        # Métricas exclusivas del subconjunto de apuestas
        if bet_y_true:
            bet_brier = brier_score_loss(bet_y_true, bet_y_prob)
            bet_logloss = log_loss(bet_y_true, bet_y_prob)
            print(f"Muestra Operativa:    {stats['bets']} apuestas ejecutadas")
            print(f"Calibración Operativa:Brier={bet_brier:.4f} | Log Loss={bet_logloss:.4f}")
            print("-" * 70)
        
        ganancia_bruta = stats['won'] * (stats['flat_profit'] / stats['won'] if stats['won'] > 0 else 0)
        perdida_bruta = abs(stats['bets'] - stats['won'])
        # Profit Factor Real (Ganancia bruta / Pérdida bruta)
        profit_factor = stats['gross_won'] / stats['gross_lost'] if stats['gross_lost'] > 0 else float('inf')

        print(f"Muestra Operativa:    {stats['bets']} apuestas de {stats['total_games']} juegos")
        print(f"Brier Score:          {brier:.4f}  |  Log Loss: {logloss:.4f}")
        print(f"Sharpness:            {sharpness:.3f} (Ideal 0.13 - 0.17)")
        print("-" * 70)
        print(f"Precisión Real:       {win_rate:.2f}%")
        print(f"Alpha Promedio:       {avg_edge:+.2f}%")
        print(f"Profit Factor:        {profit_factor:.2f} (Ideal > 1.10)")
        print(f"BANKROLL FINAL:       ${bankroll:.2f} ({((bankroll-STARTING_BANKROLL)/STARTING_BANKROLL)*100:+.2f}%)")
        
        return {
            'roi': roi,
            'win_rate': win_rate,
            'bets': stats['bets'],
            'y_true': y_true,
            'y_prob': y_prob,
            'final_bankroll': bankroll
        }
    else:
        print("El modelo no encontró valor real en esta muestra.")
        # FIX ALTO: Devolver vectores de probabilidad para que el Grid Search calcule el Brier Score
        if y_true:
            return {
                'roi': 0.0, 
                'win_rate': 0.0, 
                'bets': 0, 
                'y_true': y_true, 
                'y_prob': y_prob, 
                'final_bankroll': bankroll
            }
        return None
    # =====================================================================
# EJECUCIÓN INDEPENDIENTE (Para cuando solo quieres hacer Backtest)
# =====================================================================
if __name__ == "__main__":
    FECHA_INICIO = "2025-08-01" 
    DIAS_A_SIMULAR = 15 

    resultados = run_master_backtest(
        start_date_str=FECHA_INICIO, 
        days=DIAS_A_SIMULAR, 
        use_hot_hand=USE_HOT_HAND_GLOBAL 
    )