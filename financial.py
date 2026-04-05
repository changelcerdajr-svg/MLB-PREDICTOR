# financial.py - Motor de Riesgo Institucional V17.9 (Shin Optimized)
from scipy.optimize import brentq
from config import KELLY_FRACTION

def american_to_prob(odds: int) -> float:
    """Convierte un momio americano a probabilidad implícita."""
    if odds > 0:
        return 100.0 / (odds + 100.0)
    else:
        return abs(odds) / (abs(odds) + 100.0)
    
def calculate_kelly(prob_win, american_odds, fraction=KELLY_FRACTION):
    """
    Calcula el tamaño de la apuesta usando el Criterio de Kelly fraccionado (V18.0).
    fraction: 0.25 para 1/4 Kelly (Gestión de riesgo institucional).
    """
    # 0. Validación de seguridad contra momios rotos (cero)
    if not american_odds or american_odds == 0:
        return 0.0
        
    # 1. Calcular el pago neto 'b' (decimal odds - 1)
    if american_odds > 0:
        b = american_odds / 100.0
    else:
        b = 100.0 / abs(american_odds)
    
    # 2. Probabilidad de pérdida
    q = 1.0 - prob_win
    
    # 3. Fórmula de Kelly: f* = (bp - q) / b
    f_star = (b * prob_win - q) / b
    
    # 4. Aplicar fracción y proteger contra valores negativos (sin apuesta)
    return max(0.0, f_star * fraction)

def get_fair_prob(h_odds: int, a_odds: int):
    """
    Limpia la comisión (vig) del casino usando el Método de Shin.
    Retorna la probabilidad real (Fair Value) del local y visitante.
    """
    # 1. Validación de seguridad contra momios nulos o corruptos
    if not h_odds or not a_odds or h_odds == 0 or a_odds == 0:
        return 0.5, 0.5  # Retorna moneda al aire si los datos están rotos

    pi_h = american_to_prob(h_odds)
    pi_a = american_to_prob(a_odds)
    
    total_implied = pi_h + pi_a
    
    # 2. Protección contra División por Cero
    if total_implied == 0:
        return 0.5, 0.5
        
    margin = total_implied - 1.0

    # Si por alguna razón no hay vig (raro), devolvemos las probabilidades normalizadas
    if margin <= 0:
        return pi_h / total_implied, pi_a / total_implied

    # Función objetivo para el método de Shin
    def shin_objective(z, p1, p2):
        def calc_p(pi, z_val):
            return ( (z_val**2 + 4*(1-z_val)*(pi**2 / (p1+p2)))**0.5 - z_val ) / (2*(1-z_val))
        return calc_p(p1, z) + calc_p(p2, z) - 1.0

    try:
        # Resolvemos z (proporción de insider trading asumida en el mercado)
        z = brentq(shin_objective, 0.0, 0.4, args=(pi_h, pi_a))
        
        def calc_fair(pi, z_val, total_pi):
            return ( (z_val**2 + 4*(1-z_val)*(pi**2 / total_pi))**0.5 - z_val ) / (2*(1-z_val))
            
        fair_h = calc_fair(pi_h, z, total_implied)
        fair_a = calc_fair(pi_a, z, total_implied)
        
        return fair_h, fair_a
    except:
        # Fallback de seguridad: Normalización proporcional clásica
        return pi_h / total_implied, pi_a / total_implied

def calculate_edge(model_prob: float, market_prob_clean: float) -> dict:
    """
    Calcula la ventaja real sobre el mercado y asigna la fracción de Kelly.
    """
    edge = model_prob - market_prob_clean
    
    # Cálculo de Kelly Criterion (Usamos Quarter-Kelly por seguridad)
    if edge > 0:
        # b es el multiplicador de ganancia neta en base a la prob del mercado
        b = (1.0 / market_prob_clean) - 1.0
        full_kelly = edge / b
        kelly_fraction = max(0.0, full_kelly * KELLY_FRACTION)
    else:
        kelly_fraction = 0.0

    # Asignación de Grado / Veredicto
    verdict = "NO PLAY"
    if edge >= 0.04:
        verdict = "HIGH VALUE"
    elif edge > 0.015:
        verdict = "VALUE"

    return {
        "edge": edge,
        "edge_pct": f"{edge*100:+.2f}%",
        "verdict": verdict,
        "kelly": kelly_fraction
    }