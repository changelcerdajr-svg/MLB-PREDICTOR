# umpire.py
from config import UMPIRE_FACTORS

class UmpireEngine:
    def get_game_umpire(self):
        """
        V11.5: Purgado de ruido estocástico falso.
        Si no sabemos con certeza quién es el umpire, usamos estrictamente el DEFAULT (1.00).
        Nada de inyectar varianza aleatoria.
        """
        # En un entorno de producción avanzado, aquí harías scraping del umpire asignado.
        # Por ahora, para evitar inyectar ruido falso, asumimos neutralidad estricta:
        name = 'DEFAULT'
        factor = UMPIRE_FACTORS.get(name, 1.00)
        
        return {
            'name': 'Árbitro Promedio (Neutral)', 
            'factor': factor, 
            'description': 'Zona Neutral (Sin sesgo)'
        }