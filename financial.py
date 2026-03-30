# financial.py
# Motor de Riesgo Financiero y Gestión de Capital - V11.7
# Corrección: Eliminación de Vig (Overround) y cálculo de Edge sobre Fair Value.

from scipy.optimize import brentq

def american_to_prob(odds: int) -> float:
    """
    Convierte momio americano a probabilidad implícita.
    Ejemplo: -110 -> 0.5238 | +110 -> 0.4761
    """
    if odds == 0:
        return 0.0
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)

def get_fair_prob(h_odds: int, a_odds: int) -> tuple:
    """
    Elimina el Vig usando el método proporcional (Overround).
    Es un método rápido para obtener la probabilidad 'justa'.
    Retorna (prob_home_clean, prob_away_clean)
    """
    p_h = american_to_prob(h_odds)
    p_a = american_to_prob(a_odds)
    
    overround = p_h + p_a
    if overround == 0:
        return 0.5, 0.5
        
    return p_h / overround, p_a / overround

def remove_vig(prob_home: float, prob_away: float) -> tuple:
    """
    Elimina el margen del casino usando el Power Method de Shin optimizado.
    Calcula la probabilidad real (sin vig) respetando la asimetría del mercado.
    """
    if prob_home == 0 or prob_away == 0:
        return 0.0, 0.0
        
    total_implied = prob_home + prob_away
    margin = total_implied - 1.0
    
    # Si no hay margen detectable, devolvemos los valores originales
    if margin <= 0.001:
        return prob_home, prob_away
        
    # Función objetivo para el optimizador matemático
    def objective(k):
        p1 = (prob_home ** k) / ((prob_home ** k) + (prob_away ** k))
        p2 = (prob_away ** k) / ((prob_home ** k) + (prob_away ** k))
        return p1 + p2 - 1.0
        
    try:
        # Busca el exponente k exacto donde las probabilidades sumen 1.0
        k_opt = brentq(objective, 0.1, 10.0)
    except (ValueError, RuntimeError):
        # Fallback a proporción simple si la optimización falla
        total = prob_home + prob_away
        return prob_home / total, prob_away / total

    # Probabilidad limpia final con el exponente encontrado
    p_home_clean = (prob_home ** k_opt) / ((prob_home ** k_opt) + (prob_away ** k_opt))
    p_away_clean = (prob_away ** k_opt) / ((prob_home ** k_opt) + (prob_away ** k_opt))
    
    return p_home_clean, p_away_clean

def calculate_edge(model_prob: float, market_prob_clean: float) -> dict:
    """
    Cruza la probabilidad del modelo contra la línea LIMPIA (sin Vig).
    Calcula el Edge Real y la fracción de Kelly óptima (1/4 Kelly).
    """
    if market_prob_clean <= 0 or market_prob_clean >= 1:
        return {
            "edge": 0.0,
            "edge_pct": "0.00%",
            "kelly": 0.0,
            "verdict": "ERROR: Probabilidades Inválidas"
        }

    # El Edge Real es sobre la probabilidad justa del mercado
    edge = model_prob - market_prob_clean
    
    if edge <= 0:
        return {
            "edge": edge,
            "edge_pct": f"{edge*100:.2f}%",
            "kelly": 0.0,
            "verdict": "NO VALUE (Negativo)"
        }
        
    # --- CÁLCULO DEL CRITERIO DE KELLY ---
    # b = Ganancia neta decimal (Fair Value)
    decimal_odds = 1 / market_prob_clean
    b = decimal_odds - 1
    p = model_prob
    q = 1 - p
    
    # Kelly puro (f*)
    kelly_full = (b * p - q) / b
    
    # Gestión de riesgo institucional: 1/4 de Kelly (0.25)
    quarter_kelly = max(0.0, kelly_full * 0.25)  
    
    if edge > 0.05:
        verdict = "GRADE A: HIGH VALUE"
    elif edge > 0.02:
        verdict = "GRADE B: VALUE FOUND"
    else:
        verdict = "GRADE C: MARGINAL"
    
    return {
        "edge": edge,
        "edge_pct": f"+{edge*100:.2f}%",
        "kelly": quarter_kelly,
        "verdict": verdict
    }