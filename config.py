# config.py
# Configuración Global - V12.3 (Sincronización Institucional con HFA Dinámico)

# 1. API
API_URL = "https://statsapi.mlb.com/api/v1"
USER_AGENT = "Mozilla/5.0 (MLB-Predictor-Pro/12.3)"

# 2. SIMULACIÓN
SIMULATION_ROUNDS = 10000     # Optimizado para convergencia estadística
STRESS_TEST_ROUNDS = 2000     # Para el cálculo de Sensibilidad (Stress Testing)

# 3. FACTORES DE PARQUE (Park Factors - Base Carreras Totales)
# > 1.00 = Favorece Ofensiva | < 1.00 = Favorece Pitcheo
PARK_FACTORS = {
    'runs': {
        19: 1.35,  # Coors Field (COL)
        18: 1.12,  # Great American Ball Park (CIN)
        9:  1.08,  # Fenway Park (BOS)
        7:  1.06,  # Kauffman Stadium (KC)
        12: 1.05,  # Guaranteed Rate Field (CWS)
        33: 1.05,  # Yankee Stadium (NYY)
        16: 1.04,  # Truist Park (ATL)
        17: 1.04,  # Wrigley Field (CHC)
        22: 1.04,  # Dodger Stadium (LAD)
        4:  1.03,  # PNC Park (PIT)
        11: 1.02,  # T-Mobile Park (SEA)
        25: 1.02,  # Busch Stadium (STL)
        28: 1.02,  # Globe Life Field (TEX)
        21: 1.01,  # Citizens Bank Park (PHI)
        2:  1.00,  # Oriole Park (BAL)
        1:  1.00,  # Angel Stadium (LAA)
        5:  1.00,  # Progressive Field (CLE)
        14: 1.00,  # Oakland Coliseum (OAK)
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
        30: 0.92   # Petco Park (SD)
    }
}

# 4. HOME FIELD ADVANTAGE (HFA) DINÁMICO (Punto 11 Auditoría)
# Valores calibrados según ventaja histórica de carreras del local por estadio.
STADIUM_HFA = {
    19: 1.065, # Coors Field (COL) - Altitud y fatiga extrema
    26: 1.055, # Tropicana Field (TB) - Superficie y domo
    9:  1.050, # Fenway Park (BOS) - Rebotes en el Monstruo Verde
    17: 1.048, # Wrigley Field (CHC) - Efecto del viento
    22: 1.046, # Dodger Stadium (LAD) - Aislamiento / Viaje
    33: 1.045, # Yankee Stadium (NYY)
    15: 1.045, # Chase Field (ARI)
    18: 1.043, # Great American Ball Park (CIN)
    11: 1.042, # T-Mobile Park (SEA)
    16: 1.042, # Truist Park (ATL)
    28: 1.041, # Globe Life Field (TEX)
    10: 1.041, # Rogers Centre (TOR)
    27: 1.040, # Oracle Park (SF)
    25: 1.040, # Busch Stadium (STL)
    21: 1.040, # Citizens Bank Park (PHI)
    2:  1.040, # Oriole Park (BAL)
    1:  1.040, # Angel Stadium (LAA)
    5:  1.040, # Progressive Field (CLE)
    7:  1.039, # Kauffman Stadium (KC)
    12: 1.039, # Guaranteed Rate Field (CWS)
    29: 1.039, # Nationals Park (WSH)
    3:  1.039, # Target Field (MIN)
    6:  1.038, # Comerica Park (DET)
    23: 1.038, # loanDepot park (MIA)
    32: 1.038, # American Family Field (MIL)
    4:  1.038, # PNC Park (PIT)
    24: 1.037, # Minute Maid Park (HOU)
    14: 1.037, # Oakland Coliseum (OAK)
    31: 1.036, # Citi Field (NYM)
    30: 1.035  # Petco Park (SD)
}

def get_hfa_factor(venue_id):
    """Retorna el peso real de la localía para el estadio solicitado."""
    return STADIUM_HFA.get(venue_id, 1.04)

# 5. COORDENADAS GEOGRÁFICAS COMPLETAS (Indexadas por TEAM_ID)
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

# 6. FECHA
USE_REAL_TIME = True  #
TEST_DATE = "2026-03-27" #