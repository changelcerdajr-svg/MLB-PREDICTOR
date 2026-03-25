# config.py
# Configuración Global - V3.1 (Umpires + Lineups)

# 1. API
API_URL = "https://statsapi.mlb.com/api/v1"
USER_AGENT = "Mozilla/5.0 (MLB-Predictor-Pro/3.1)"

# 2. SIMULACIÓN
SIMULATION_ROUNDS = 100000  # Subimos a 100k para estabilizar la desviación estándar

# Forzamos neutralidad si no sabemos quién es el umpire. Cero ruido Gaussiano.
UMPIRE_FACTORS = {
    'DEFAULT': 1.00
}

# 4. FACTORES DE PARQUE (30 Equipos MLB - Carreras Totales)
# > 1.00 = Paraíso de bateadores / < 1.00 = Paraíso de pitchers
PARK_FACTORS = {
    'runs': {
        19: 1.35,  # Coors Field (COL)
        1: 0.96,   # Angel Stadium (LAA)
        2: 0.99,   # Camden Yards (BAL - Post pared izquierda)
        3: 1.08,   # Fenway Park (BOS)
        4: 1.01,   # Guaranteed Rate (CWS)
        5: 1.00,   # Progressive Field (CLE)
        7: 0.99,   # Kauffman Stadium (KCR)
        10: 0.96,  # Oakland Coliseum (OAK)
        12: 0.92,  # Tropicana Field (TBR)
        14: 1.02,  # Citizens Bank (PHI)
        15: 1.00,  # Chase Field (ARI)
        17: 1.02,  # Wrigley Field (CHC)
        22: 0.98,  # Dodger Stadium (LAD)
        31: 0.97,  # PNC Park (PIT)
        32: 0.99,  # American Family (MIL)
        33: 0.98,  # Target Field (MIN)
        110: 0.92, # T-Mobile Park (SEA)
        147: 1.04, # Yankee Stadium (NYY)
        238: 1.05, # Truist Park (ATL)
        268: 0.98, # Oracle Park (SFG)
        3289: 0.95,# loanDepot park (MIA)
        2889: 1.02,# Busch Stadium (STL)
        3309: 0.99,# Nationals Park (WSH)
        3313: 1.01,# Globe Life Field (TEX)
        143: 0.99, # Petco Park (SDP)
        175: 1.01, # Comerica Park (DET)
        288: 0.99, # Rogers Centre (TOR)
        239: 1.00, # Minute Maid Park (HOU)
        134: 0.98, # Citi Field (NYM)
        113: 1.06  # Great American Ball Park (CIN)
    }
}

# 5. COORDENADAS
STADIUM_COORDS = {
    147: {'lat': 40.8296, 'lon': -73.9262},
    110: {'lat': 47.5914, 'lon': -122.3325},
    19:  {'lat': 39.7559, 'lon': -104.9942},
    119: {'lat': 34.0739, 'lon': -118.2400},
    1:   {'lat': 33.8003, 'lon': -117.8827},
    32:  {'lat': 44.9817, 'lon': -93.2777},
}

# 6. FECHA
USE_REAL_TIME = False
TEST_DATE = "2026-03-25"  # Solo para pruebas, no afecta al backtest