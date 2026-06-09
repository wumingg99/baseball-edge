import numpy as np
import pickle
import os
from datetime import datetime
import pytz

LEAGUE_AVG_TOTALS = {
    1: 8.8,   # MLB
    2: 7.5,   # NPB
    5: 8.2,   # KBO
    29: 7.8,  # CPBL
    21: 8.0,  # LMB
    22: 7.5,  # LMP
    11: 7.8,  # LIDOM
    31: 7.5,  # LVBP
    25: 7.8,  # LBPRC
    6: 7.2,   # ABL
}
DEFAULT_AVG_TOTAL = 7.5

TIER_FACTORS = {1: 1.0, 2: 0.85, 3: 0.70}

def get_league_avg(league_id):
    return LEAGUE_AVG_TOTALS.get(league_id, DEFAULT_AVG_TOTAL)

def build_features(context, total, run_line):
    try:
        hs = context.get("home_stats") or {}
        as_ = context.get("away_stats") or {}
        tier = context.get("league_tier", 2)
        league_id = context.get("league_id", 0)
        tier_factor = TIER_FACTORS.get(tier, 0.70)
        league_avg = get_league_avg(league_id)

        home_rpg = max(2.0, min(float(hs.get("runs_per_game", 4.5)), 10.0))
        away_rpg = max(2.0, min(float(as_.get("runs_per_game", 4.5)), 10.0))
        home_ra = max(2.0, min(float(hs.get("runs_allowed_per_game", 4.5)), 10.0))
        away_ra = max(2.0, min(float(as_.get("runs_allowed_per_game", 4.5)), 10.0))
        home_home_rpg = max(2.0, min(float(hs.get("home_runs_per_game", 4.8)), 10.0))
        away_away_rpg = max(2.0, min(float(as_.get("away_runs_per_game", 4.2)), 10.0))
        home_home_ra = max(2.0, min(float(hs.get("home_allowed_per_game", 4.3)), 10.0))
        away_away_ra = max(2.0, min(float(as_.get("away_allowed_per_game", 4.7)), 10.0))
        home_win_pct = float(hs.get("win_pct", 0.500))
        away_win_pct = float(as_.get("win_pct", 0.500))

        # Implied total using home/away specific splits
        implied_total = (home_home_rpg + away_away_rpg +
                         away_away_ra + home_home_ra) / 2
        implied_total = max(4.0, min(implied_total, 15.0))

        vegas_line = total if total else league_avg
        total_gap = (implied_total - vegas_line) / 2

        # Run line direction
        home_strength = (home_rpg - home_ra + (home_win_pct - 0.5) * 2)
        away_strength = (away_rpg - away_ra + (away_win_pct - 0.5) * 2)
        strength_diff = home_strength - away_strength
        run_line_norm = (run_line or (-1.5 if strength_diff > 0 else 1.5)) / 2

        rpg_sum = (home_rpg + away_rpg - 9.0) / 2
        ra_sum = (home_ra + away_ra - 9.0) / 2
        home_split = home_home_rpg - home_rpg
        away_split = away_away_rpg - away_rpg
        win_diff = home_win_pct - away_win_pct
        total_norm = (vegas_line - league_avg) / 2

        current_month = datetime.now(
            pytz.timezone("Asia/Singapore")).month
        fatigue = (1.0 if current_month <= 6 else
                   1.05 if current_month <= 8 else 1.10)

        return [
            home_rpg, away_rpg,
            home_ra, away_ra,
            home_home_rpg, away_away_rpg,
            home_home_ra, away_away_ra,
            home_win_pct, away_win_pct,
            implied_total, total_gap,
            rpg_sum, ra_sum,
            home_split, away_split,
            win_diff, strength_diff,
            run_line_norm, total_norm,
            tier_factor, fatigue,
        ]
    except Exception as e:
        print(f"Feature error: {e}")
        return None

def train_models():
    from sklearn.linear_model import LogisticRegression
    from sklearn.neural_network import MLPClassifier
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score
    from xgboost import XGBClassifier
    import numpy as np

    print("Generating simulated training data...")
    np.random.seed(42)
    X, y_total, y_runline = [], [], []

    for _ in range(1200):
        home_rpg = np.random.normal(4.5, 0.8)
        away_rpg = np.random.normal(4.5, 0.8)
        home_ra = np.random.normal(4.5, 0.8)
        away_ra = np.random.normal(4.5, 0.8)
        home_home_rpg = home_rpg * np.random.uniform(1.0, 1.15)
        away_away_rpg = away_rpg * np.random.uniform(0.85, 1.0)
        home_home_ra = home_ra * np.random.uniform(0.9, 1.1)
        away_away_ra = away_ra * np.random.uniform(0.9, 1.1)
        home_win = np.random.uniform(0.3, 0.7)
        away_win = np.random.uniform(0.3, 0.7)
        tier = np.random.choice([1, 2, 3])
        tier_factor = 1.0 if tier == 1 else 0.85 if tier == 2 else 0.70
        league_avg = np.random.choice([7.5, 8.0, 8.2, 8.8])
        total = league_avg + np.random.uniform(-1.0, 1.0)

        h_rpg_c = max(2.0, min(home_rpg, 10.0))
        a_rpg_c = max(2.0, min(away_rpg, 10.0))
        h_ra_c = max(2.0, min(home_ra, 10.0))
        a_ra_c = max(2.0, min(away_ra, 10.0))
        h_home = max(2.0, min(home_home_rpg, 10.0))
        a_away = max(2.0, min(away_away_rpg, 10.0))
        h_home_ra = max(2.0, min(home_home_ra, 10.0))
        a_away_ra = max(2.0, min(away_away_ra, 10.0))

        implied = (h_home + a_away + a_away_ra + h_home_ra) / 2
        implied = max(4.0, min(implied, 15.0))
        total_gap = (implied - total) / 2

        home_str = (h_rpg_c - h_ra_c + (home_win - 0.5) * 2)
        away_str = (a_rpg_c - a_ra_c + (away_win - 0.5) * 2)
        str_diff = home_str - away_str
        rl_norm = (-1.5 if str_diff > 0 else 1.5) / 2

        features = [
            h_rpg_c, a_rpg_c, h_ra_c, a_ra_c,
            h_home, a_away, h_home_ra, a_away_ra,
            home_win, away_win,
            implied, total_gap,
            (h_rpg_c + a_rpg_c - 9.0) / 2,
            (h_ra_c + a_ra_c - 9.0) / 2,
            h_home - h_rpg_c, a_away - a_rpg_c,
            home_win - away_win, str_diff,
            rl_norm, (total - league_avg) / 2,
            tier_factor, 1.0,
        ]

        noise = np.random.normal(0, 1.5)
        actual = implied + noise
        goes_over = 1 if actual > total else 0
        margin = str_diff * 0.5 + np.random.normal(0, 2.0)
        covers_rl = 1 if margin > 1.5 else 0

        X.append(features)
        y_total.append(goes_over)
        y_runline.append(covers_rl)

    X = np.array(X)
    y_total = np.array(y_total)
    y_runline = np.array(y_runline)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    X_train, X_test, yt_train, yt_test = train_test_split(
        X_scaled, y_total, test_size=0.2, random_state=42)
    _, _, yr_train, yr_test = train_test_split(
        X_scaled, y_runline, test_size=0.2, random_state=42)

    models_total = {}
    models_runline = {}
    for name, ct, cr in [
        ("lr",
         LogisticRegression(max_iter=1000, random_state=42),
         LogisticRegression(max_iter=1000, random_state=42)),
        ("rf",
         RandomForestClassifier(n_estimators=100, random_state=42),
         RandomForestClassifier(n_estimators=100, random_state=42)),
        ("xgb",
         XGBClassifier(n_estimators=100, max_depth=4, learning_rate=0.1,
                       random_state=42, eval_metric="logloss", verbosity=0),
         XGBClassifier(n_estimators=100, max_depth=4, learning_rate=0.1,
                       random_state=42, eval_metric="logloss", verbosity=0)),
        ("nn",
         MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=2000, random_state=42),
         MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=2000, random_state=42)),
    ]:
        ct.fit(X_train, yt_train)
        models_total[name] = ct
        cr.fit(X_train, yr_train)
        models_runline[name] = cr

    with open("models.pkl", "wb") as f:
        pickle.dump({
            "models_total": models_total,
            "models_runline": models_runline,
            "scaler": scaler
        }, f)
    print("Simulated models saved.")
    return models_total, models_runline, scaler

def load_models():
    if os.path.exists("models.pkl"):
        with open("models.pkl", "rb") as f:
            data = pickle.load(f)
        if "models_runline" in data:
            return data["models_total"], data["models_runline"], data["scaler"]
    return None, None, None

def ensemble_predict(models, X_scaled):
    weights = {"lr": 1, "rf": 2, "xgb": 3, "nn": 2}
    weighted_prob = 0
    total_weight = 0
    yes_votes = no_votes = 0
    for name, model in models.items():
        prob = model.predict_proba(X_scaled)[0][1]
        w = weights.get(name, 1)
        weighted_prob += prob * w
        total_weight += w
        if prob > 0.5:
            yes_votes += 1
        else:
            no_votes += 1
    avg_prob = weighted_prob / total_weight
    return avg_prob, yes_votes, no_votes, len(models)

def monte_carlo_simulate(context, total, run_line, n=10000):
    np.random.seed(None)
    hs = context.get("home_stats") or {}
    as_ = context.get("away_stats") or {}
    league_id = context.get("league_id", 0)
    league_avg = get_league_avg(league_id)

    home_rpg = max(2.0, min(float(hs.get("home_runs_per_game", 4.8)), 10.0))
    away_rpg = max(2.0, min(float(as_.get("away_runs_per_game", 4.2)), 10.0))
    home_ra = max(2.0, min(float(hs.get("home_allowed_per_game", 4.3)), 10.0))
    away_ra = max(2.0, min(float(as_.get("away_allowed_per_game", 4.7)), 10.0))

    home_expected = (home_rpg + away_ra) / 2
    away_expected = (away_rpg + home_ra) / 2
    home_expected = max(2.0, home_expected)
    away_expected = max(2.0, away_expected)

    home_scores = np.random.poisson(home_expected, n)
    away_scores = np.random.poisson(away_expected, n)
    totals = home_scores + away_scores

    home_wins = np.sum(home_scores > away_scores)
    ties = np.sum(home_scores == away_scores)
    home_wins_final = home_wins + int(ties * 0.54)

    vegas = total if total else league_avg
    return {
        "home_win_prob": round(home_wins_final / n, 3),
        "away_win_prob": round(1 - home_wins_final / n, 3),
        "over_prob": round(np.sum(totals > vegas) / n, 3),
        "simulated_avg_total": round(float(np.mean(totals)), 1),
    }

def predict_game(context, total, run_line):
    models_total, models_runline, scaler = load_models()
    if models_total is None:
        train_models()
        models_total, models_runline, scaler = load_models()

    features = build_features(context, total, run_line)
    if features is None:
        return None

    f = np.array(features).reshape(1, -1)
    try:
        f_scaled = scaler.transform(f)
    except Exception:
        train_models()
        models_total, models_runline, scaler = load_models()
        f_scaled = scaler.transform(f)

    total_prob, total_yes, total_no, total_count = ensemble_predict(
        models_total, f_scaled)
    rl_prob, rl_yes, rl_no, rl_count = ensemble_predict(
        models_runline, f_scaled)

    mc = monte_carlo_simulate(context, total, run_line)

    hs = context.get("home_stats") or {}
    as_ = context.get("away_stats") or {}
    league_id = context.get("league_id", 0)
    league_avg = get_league_avg(league_id)

    home_rpg = float(hs.get("home_runs_per_game", 4.8))
    away_rpg = float(as_.get("away_runs_per_game", 4.2))
    home_ra = float(hs.get("home_allowed_per_game", 4.3))
    away_ra = float(as_.get("away_allowed_per_game", 4.7))

    implied_total = (home_rpg + away_rpg + away_ra + home_ra) / 2
    implied_total = max(4.0, min(implied_total, 15.0))
    our_total = round(implied_total, 1)
    vegas_line = total if total else league_avg
    total_gap = round(our_total - vegas_line, 1)

    if total_gap > 0:
        total_pred = "OVER"
        total_votes = total_yes
        total_conf = round(total_prob * 100, 1)
    else:
        total_pred = "UNDER"
        total_votes = total_no
        total_conf = round((1 - total_prob) * 100, 1)

    home_is_fav = (run_line or -1.5) < 0
    if rl_prob > 0.5:
        rl_pred = "HOME -1.5" if home_is_fav else "HOME +1.5"
        rl_votes = rl_yes
    else:
        rl_pred = "AWAY +1.5" if home_is_fav else "AWAY -1.5"
        rl_votes = rl_no
    rl_conf = round(max(rl_prob, 1 - rl_prob) * 100, 1)

    home_win_prob = round(mc["home_win_prob"] * 0.6 + rl_prob * 0.4, 3)

    from config import MIN_MODELS_AGREE, MIN_CONFIDENCE, RL_MIN_CONFIDENCE, EDGE_THRESHOLD
    edge_flagged = (
        abs(total_gap) >= EDGE_THRESHOLD and
        total_votes >= MIN_MODELS_AGREE and
        total_conf >= MIN_CONFIDENCE
    )
    rl_edge_flagged = (
        rl_votes >= MIN_MODELS_AGREE and
        rl_conf >= RL_MIN_CONFIDENCE
    )

    return {
        "our_total": our_total,
        "total_gap": total_gap,
        "total_pred": total_pred,
        "total_conf": total_conf,
        "total_votes": total_votes,
        "total_models": total_count,
        "rl_pred": rl_pred,
        "rl_conf": rl_conf,
        "rl_votes": rl_votes,
        "rl_models": rl_count,
        "home_win_prob": home_win_prob,
        "away_win_prob": round(1 - home_win_prob, 3),
        "mc_avg_total": mc["simulated_avg_total"],
        "mc_over_prob": mc["over_prob"],
        "edge_flagged": edge_flagged,
        "rl_edge_flagged": rl_edge_flagged,
        "league_avg": league_avg,
        "has_data": hs.get("games_played", 0) > 5,
    }
