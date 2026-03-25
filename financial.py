# financial.py
# Motor de Riesgo Financiero y Gestión de Capital

def american_to_prob(odds: int) -> float:
    """Convierte momio americano a probabilidad implícita."""
    if odds == 0:
        return 0.0
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)

def remove_vig(prob_home: float, prob_away: float) -> tuple:
    """Elimina el margen del casino (Vig) por Normalización Proporcional."""
    if prob_home == 0 or prob_away == 0:
        return 0.0, 0.0
    total = prob_home + prob_away
    return prob_home / total, prob_away / total

def calculate_edge(model_prob: float, market_prob: float) -> dict:
    """
    Cruza la probabilidad empírica del modelo contra la línea limpia del mercado.
    Calcula el Edge (Margen) y la fracción de Kelly óptima.
    """
    if market_prob == 0:
        return {
            "edge": 0.0,
            "edge_pct": "0.00%",
            "kelly": 0.0,
            "verdict": "Esperando momios válidos..."
        }

    edge = model_prob - market_prob
    
    # Si no hay ventaja matemática, no se apuesta.
    if edge <= 0:
        return {
            "edge": edge,
            "edge_pct": f"{edge*100:.2f}%",
            "kelly": 0.0,
            "verdict": "CERO VALOR (No Apostar)"
        }