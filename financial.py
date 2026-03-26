# financial.py
# Motor de Riesgo Financiero y Gestión de Capital - V11.5

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

from scipy.optimize import brentq

def remove_vig(prob_home: float, prob_away: float) -> tuple:
    """
    Elimina el margen del casino usando el Power Method de Shin optimizado.
    Calcula la probabilidad real (sin vig) respetando la asimetría del mercado.
    """
    if prob_home == 0 or prob_away == 0:
        return 0.0, 0.0
        
    total_implied = prob_home + prob_away
    margin = total_implied - 1.0
    
    if margin <= 0.001:
        return prob_home, prob_away
        
    # Función objetivo para el optimizador matemático
    def objective(k):
        p1 = (prob_home ** k) / ((prob_home ** k) + (prob_away ** k))
        p2 = (prob_away ** k) / ((prob_home ** k) + (prob_away ** k))
        return p1 + p2 - 1.0
        
    try:
        # Brentq busca el exponente k exacto donde las probabilidades sumen 1.0
        # Buscamos en el rango seguro de 0.1 a 10.0
        k_opt = brentq(objective, 0.1, 10.0)
    except ValueError:
        # Si la optimización falla por valores extremos, usamos proporción simple
        return prob_home / total_implied, prob_away / total_implied

    # Calculamos la probabilidad limpia final con el exponente encontrado
    p_home_clean = (prob_home ** k_opt) / ((prob_home ** k_opt) + (prob_away ** k_opt))
    p_away_clean = (prob_away ** k_opt) / ((prob_home ** k_opt) + (prob_away ** k_opt))
    
    return p_home_clean, p_away_clean

def calculate_edge(model_prob: float, market_prob: float) -> dict:
    """
    Cruza la probabilidad empírica del modelo contra la línea limpia del mercado.
    Calcula el Edge (Ventaja) y la fracción de Kelly óptima.
    """
    if market_prob <= 0 or market_prob >= 1:
        return {
            "edge": 0.0,
            "edge_pct": "0.00%",
            "kelly": 0.0,
            "verdict": "Esperando momios válidos..."
        }

    # El Edge es la diferencia entre nuestra predicción y la del mercado
    edge = model_prob - market_prob
    
    # Si no hay ventaja matemática (Edge negativo), no se apuesta.
    if edge <= 0:
        return {
            "edge": edge,
            "edge_pct": f"{edge*100:.2f}%",
            "kelly": 0.0,
            "verdict": "CERO VALOR (No Apostar)"
        }
        
    # --- CÁLCULO DEL CRITERIO DE KELLY ---
    # La fórmula f* = (bp - q) / b
    # b = Ganancia neta decimal (Cuanto ganas por cada peso apostado)
    # p = Probabilidad de ganar (Modelo)
    # q = Probabilidad de perder (1 - p)
    
    decimal_odds = 1 / market_prob
    b = decimal_odds - 1
    p = model_prob
    q = 1 - p
    
    # Kelly puro (f*)
    kelly_full = (b * p - q) / b
    
    # --- GESTIÓN DE RIESGO (KELLY FRACCIONARIO) ---
    # Usamos 1/4 de Kelly (0.25) para absorber la varianza del béisbol 
    # y protegernos de errores de estimación del modelo.
    quarter_kelly = max(0.0, kelly_full * 0.25)  
    
    # Definición del veredicto basado en la magnitud de la ventaja
    if edge > 0.05:
        verdict = "VALOR ALTO (Inversión Recomendada)"
    elif edge > 0.02:
        verdict = "VALOR REAL"
    else:
        verdict = "VALOR MARGINAL (Proceder con cautela)"
    
    return {
        "edge": edge,
        "edge_pct": f"+{edge*100:.2f}%",
        "kelly": quarter_kelly,
        "verdict": verdict
    }