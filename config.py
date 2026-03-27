# config.py
# Configuración Global - V12.2 (Sincronización Institucional)

# 1. API
API_URL = "https://statsapi.mlb.com/api/v1"
USER_AGENT = "Mozilla/5.0 (MLB-Predictor-Pro/12.2)"

# 2. SIMULACIÓN
SIMULATION_ROUNDS = 10000     # Optimizado (Reemplaza los 100k innecesarios)
STRESS_TEST_ROUNDS = 2000     # Para el cálculo de Sensibilidad

# 3. FACTORES DE PARQUE (30 Equipos MLB - Carreras Totales)
# Factores de Estadio Reales (Park Factors 2024 - Base Histórica)
# > 1.00 = Favorece Carreras | < 1.00 = Favorece Pitcheo
# IDs Verificados con la API de Stats de MLB
PARK_FACTORS = {
    'runs': {
        19: 1.35,  # Coors Field (COL) - El más extremo
        18: 1.12,  # Great American Ball Park (CIN)
        9:  1.08,  # Fenway Park (BOS)
        7:  1.06,  # Kauffman Stadium (KC)
        12: 1.05,  # Guaranteed Rate Field (CWS)
        33: 1.05,  # Yankee Stadium (NYY) - *Nota: ID API es 33 (antes 32 en algunas docs)
        16: 1.04,  # Truist Park (ATL)
        17: 1.04,  # Wrigley Field (CHC)
        22: 1.04,  # Dodger Stadium (LAD)
        4:  1.03,  # PNC Park (PIT)
        11: 1.02,  # T-Mobile Park (SEA)
        25: 1.02,  # Busch Stadium (STL)
        28: 1.02,  # Globe Life Field (TEX)
        21: 1.01,  # Citizens Bank Park (PHI)
        2:  1.00,  # Oriole Park (BAL) - Neutro post-muro
        1:  1.00,  # Angel Stadium (LAA)
        5:  1.00,  # Progressive Field (CLE)
        14: 1.00,  # Oakland Coliseum (OAK) - *Temporal hasta Las Vegas
        15: 1.00,  # Chase Field (ARI)
        26: 1.00,  # Tropicana Field (TB)
        29: 1.00,  # Nationals Park (WSH)
        3:  0.99,  # Target Field (MIN)
        6:  0.99,  # Comerica Park (DET)
        23: 0.98,  # loanDepot park (MIA)
        10: 0.98,  # Rogers Centre (TOR)
        27: 0.98,  # Oracle Park (SF)
        31: 0.96,  # Citi Field (NYM)
        24: 0.95,  # Minute Maid Park (HOU)
        32: 0.94,  # American Family Field (MIL)
        30: 0.92   # Petco Park (SD) - El más hostil para bateadores
    }
}

# 4. COORDENADAS GEOGRÁFICAS COMPLETAS (30 Estadios)
# Indexadas estrictamente por TEAM_ID para cruzar con el calendario
STADIUM_COORDS = {
    108: {'lat': 33.8003, 'lon': -117.8827}, # LAA
    109: {'lat': 33.4455, 'lon': -112.0667}, # ARI
    110: {'lat': 39.2840, 'lon': -76.6215},  # BAL
    111: {'lat': 42.3467, 'lon': -71.0972},  # BOS
    112: {'lat': 41.9484, 'lon': -87.6553},  # CHC
    113: {'lat': 39.0979, 'lon': -84.5072},  # CIN
    114: {'lat': 41.4962, 'lon': -81.6852},  # CLE
    115: {'lat': 39.7559, 'lon': -104.9942}, # COL
    116: {'lat': 42.3390, 'lon': -83.0485},  # DET
    117: {'lat': 29.7573, 'lon': -95.3555},  # HOU
    118: {'lat': 39.0517, 'lon': -94.4803},  # KC
    119: {'lat': 34.0739, 'lon': -118.2400}, # LAD
    120: {'lat': 38.8730, 'lon': -77.0074},  # WSH
    121: {'lat': 40.7571, 'lon': -73.8458},  # NYM
    133: {'lat': 37.7516, 'lon': -122.2005}, # OAK
    134: {'lat': 40.4469, 'lon': -80.0057},  # PIT
    135: {'lat': 32.7076, 'lon': -117.1570}, # SD
    136: {'lat': 47.5914, 'lon': -122.3325}, # SEA
    137: {'lat': 37.7786, 'lon': -122.3893}, # SF
    138: {'lat': 38.6226, 'lon': -90.1928},  # STL
    139: {'lat': 27.7682, 'lon': -82.6534},  # TB
    140: {'lat': 32.7512, 'lon': -97.0832},  # TEX
    141: {'lat': 43.6414, 'lon': -79.3894},  # TOR
    142: {'lat': 44.9817, 'lon': -93.2777},  # MIN
    143: {'lat': 39.9061, 'lon': -75.1665},  # PHI
    144: {'lat': 33.8908, 'lon': -84.4678},  # ATL
    145: {'lat': 41.8299, 'lon': -87.6338},  # CWS
    146: {'lat': 25.7781, 'lon': -80.2195},  # MIA
    147: {'lat': 40.8296, 'lon': -73.9262},  # NYY
    158: {'lat': 43.0280, 'lon': -87.9712}   # MIL
}

# 5. FECHA
USE_REAL_TIME = True  # Cámbialo a False si quieres usar una fecha de prueba
TEST_DATE = "2026-03-27" # Esta es la fecha que usará el modelo si USE_REAL_TIME es False