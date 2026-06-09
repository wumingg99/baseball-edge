import os
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Singapore")

API_BASEBALL_BASE = "https://v1.baseball.api-sports.io"
API_HEADERS = {"x-apisports-key": API_FOOTBALL_KEY}

EDGE_THRESHOLD = 1.5
MIN_CONFIDENCE = 54
MIN_MODELS_AGREE = 3
RL_MIN_CONFIDENCE = 65.0

# League tiers — affects model weighting
LEAGUE_TIERS = {
    # 1: MLB excluded — covered by dedicated MLB bot
    2:  {"name": "NPB",          "country": "Japan",         "tier": 1},
    5:  {"name": "KBO",          "country": "South Korea",   "tier": 1},
    29: {"name": "CPBL",         "country": "Taiwan",        "tier": 1},
    21: {"name": "LMB",          "country": "Mexico",        "tier": 2},
    22: {"name": "LMP",          "country": "Mexico",        "tier": 2},
    11: {"name": "LIDOM",        "country": "Dominican Rep", "tier": 2},
    31: {"name": "LVBP",         "country": "Venezuela",     "tier": 2},
    25: {"name": "LBPRC",        "country": "Puerto Rico",   "tier": 2},
    6:  {"name": "ABL",          "country": "Australia",     "tier": 2},
    39: {"name": "Caribbean",    "country": "Caribbean",     "tier": 2},
    17: {"name": "IBL",          "country": "Italy",         "tier": 3},
    27: {"name": "Elitserien",   "country": "Sweden",        "tier": 3},
    24: {"name": "NBL",          "country": "Norway",        "tier": 3},
    12: {"name": "SM-sarja",     "country": "Finland",       "tier": 3},
    9:  {"name": "Serie Nacional","country": "Cuba",         "tier": 3},
    63: {"name": "Liga Elite",   "country": "Cuba",          "tier": 3},
    20: {"name": "LBL",          "country": "Lithuania",     "tier": 3},
    57: {"name": "LMBP",         "country": "Venezuela",     "tier": 3},
    28: {"name": "NLA",          "country": "Switzerland",   "tier": 3},
    26: {"name": "Division Honor","country": "Spain",        "tier": 3},
    13: {"name": "Division 1",   "country": "France",        "tier": 3},
    8:  {"name": "LCBP",         "country": "Colombia",      "tier": 3},
    49: {"name": "LPB",          "country": "Colombia",      "tier": 3},
    7:  {"name": "ABL",          "country": "Austria",       "tier": 3},
    48: {"name": "Bundesliga",   "country": "Austria",       "tier": 3},
    10: {"name": "Extraliga",    "country": "Czech Rep",     "tier": 3},
    16: {"name": "Bundesliga",   "country": "Germany",       "tier": 3},
    14: {"name": "Bundesliga N", "country": "Germany",       "tier": 3},
    15: {"name": "Bundesliga S", "country": "Germany",       "tier": 3},
    23: {"name": "Hoofdklasse",  "country": "Netherlands",   "tier": 3},
    30: {"name": "NBL",          "country": "UK",            "tier": 3},
    62: {"name": "Division 1",   "country": "Belgium",       "tier": 3},
    52: {"name": "CNBS",         "country": "Nicaragua",     "tier": 3},
    54: {"name": "Championship", "country": "Russia",        "tier": 3},
    # Skip minor leagues and tournaments
    # 3,4,33,51,55,56,60,61,67,71 = minor/development leagues
    # 32,34,35,36,37,38,40,41,42,43,44,45,46,47,58,59,65,66,68,69,70,72,73,74,75,76,77 = tournaments
}

TIER_FACTORS = {1: 1.0, 2: 0.85, 3: 0.70}
