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
        1: 0.99,   # Angel Stadium
        2: 0.96,   # Oriole Park
        3: 1.00,   # Tropicana Field
        5: 1.02,   # Progressive Field
        7: 1.03,   # Kauffman Stadium
        8: 0.97,   # Comerica Park
        9: 1.07,   # Fenway Park
        10: 1.01,  # Rogers Centre
        11: 0.92,  # T-Mobile Park
        12: 1.01,  # Guaranteed Rate Field
        13: 1.00,  # Target Field
        14: 0.94,  # Oakland Coliseum
        15: 1.00,  # Chase Field
        16: 1.03,  # Truist Park
        17: 1.02,  # Wrigley Field
        18: 1.12,  # Great American Ball Park
        19: 1.34,  # Coors Field
        20: 1.01,  # American Family Field
        21: 1.03,  # Citizens Bank Park
        22: 1.00,  # Dodger Stadium
        23: 0.97,  # Nationals Park
        24: 0.97,  # Oracle Park
        25: 0.90,  # Petco Park (Pitcher friendly)
        26: 0.96,  # Busch Stadium
        27: 1.02,  # Globe Life Field
        29: 0.97,  # loanDepot park
        30: 0.97,  # PNC Park
        31: 0.95,  # Citi Field
        32: 1.05,  # Yankee Stadium (Hitter friendly)
        33: 0.95   # Minute Maid Park
    }
}

# --- CONSTANTES DE AUDITORÍA V17.9 ---
RAW_WOBA_REGRESSOR = 0.885 
LINEUP_PA_VOLUME_MULTIPLIERS = [1.32, 1.28, 1.15, 1.05, 1.00, 0.92, 0.85, 0.78, 0.65]

# 4. HOME FIELD ADVANTAGE (HFA) DINÁMICO
# Mapeo oficial de HFA calibrado por Venue ID de la MLB API
STADIUM_HFA = {
    1: 1.040,  # Angel Stadium (LAA)
    2: 1.040,  # Oriole Park (BAL)
    3: 1.055,  # Tropicana Field (TB) - Domo, alto rebote
    5: 1.040,  # Progressive Field (CLE)
    7: 1.040,  # Kauffman Stadium (KC)
    8: 1.040,  # Comerica Park (DET)
    9: 1.045,  # Fenway Park (BOS)
    10: 1.045, # Rogers Centre (TOR)
    11: 1.040, # T-Mobile Park (SEA)
    12: 1.040, # Guaranteed Rate Field (CWS)
    13: 1.040, # Target Field (MIN)
    14: 1.040, # Oakland Coliseum (OAK)
    15: 1.040, # Chase Field (AZ)
    16: 1.040, # Truist Park (ATL)
    17: 1.040, # Wrigley Field (CHC)
    18: 1.040, # Great American Ball Park (CIN)
    19: 1.060, # Coors Field (COL) - Altitud extrema
    20: 1.040, # American Family Field (MIL)
    21: 1.040, # Citizens Bank Park (PHI)
    22: 1.040, # Dodger Stadium (LAD)
    23: 1.040, # Nationals Park (WSH)
    24: 1.040, # Oracle Park (SF)
    25: 1.040, # Petco Park (SD)
    26: 1.035, # Busch Stadium (STL)
    27: 1.041, # Globe Life Field (TEX)
    29: 1.040, # loanDepot park (MIA)
    30: 1.040, # PNC Park (PIT)
    31: 1.040, # Citi Field (NYM)
    32: 1.045, # Yankee Stadium (NYY)
    33: 1.037  # Minute Maid Park (HOU)
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