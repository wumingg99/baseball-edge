import requests
import numpy as np
import pickle
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")
from config import API_BASEBALL_BASE, API_HEADERS, LEAGUE_TIERS, TIER_FACTORS

LEAGUE_AVG_TOTALS = {
    1: 8.8, 2: 7.5, 5: 8.2, 29: 7.8,
    21: 8.0, 22: 7.5, 11: 7.8, 31: 7.5,
    25: 7.8, 6: 7.2,
}
DEFAULT_AVG_TOTAL = 7.5

SEASON_WEIGHTS = {
    2023: 0.5, 2024: 0.75, 2025: 1.0, 2026: 2.0
}

def get_league_avg(league_id):
    return LEAGUE_AVG_TOTALS.get(league_id, DEFAULT_AVG_TOTAL)

def get_season_games(league_id, season):
    print(f"  Fetching league {league_id} season {season}...", flush=True)
    games = []
    try:
        url = f"{API_BASEBALL_BASE}/games"
        params = {"league": league_id, "season": season}
        r = requests.get(url, headers=API_HEADERS, params=params, timeout=30)
        if r.status_code != 200:
            return games
        data = r.json()
        for game in data.get("response", []):
            status = game.get("status", {}).get("short", "")
            if status not in ["FT", "Finished", "F"]:
                continue
            home = game.get("teams", {}).get("home", {})
            away = game.get("teams", {}).get("away", {})
            scores = game.get("scores", {})
            home_score = scores.get("home", {}).get("total")
            away_score = scores.get("away", {}).get("total")
            if home_score is None or away_score is None:
                continue
            date_str = game.get("date", "")[:10]
            month = int(date_str[5:7]) if len(date_str) >= 7 else 6
            games.append({
                "game_id": game.get("id"),
                "date": date_str,
                "season": season,
                "month": month,
                "league_id": league_id,
                "home_id": home.get("id"),
                "away_id": away.get("id"),
                "home_team": home.get("name", ""),
                "away_team": away.get("name", ""),
                "home_score": int(home_score),
                "away_score": int(away_score),
                "total": int(home_score) + int(away_score),
            })
    except Exception as e:
        print(f"  Error league {league_id} season {season}: {e}")
    return games

def get_team_stats_on_date(team_id, league_id, season):
    try:
        url = f"{API_BASEBALL_BASE}/teams/statistics"
        params = {"league": league_id, "season": season, "team": team_id}
        r = requests.get(url, headers=API_HEADERS, params=params, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json().get("response", {})
        if not data:
            return None
        games = data.get("games", {})
        points = data.get("points", {})
        wins_all = games.get("wins", {}).get("all", {})
        games_played = games.get("played", {}).get("all", 1) or 1
        wins = int(wins_all.get("total", 0) or 0)
        pts_for = points.get("for", {})
        pts_against = points.get("against", {})
        return {
            "runs_per_game": float(
                pts_for.get("average", {}).get("all", 4.5) or 4.5),
            "runs_allowed_per_game": float(
                pts_against.get("average", {}).get("all", 4.5) or 4.5),
            "home_runs_per_game": float(
                pts_for.get("average", {}).get("home", 4.5) or 4.5),
            "away_runs_per_game": float(
                pts_for.get("average", {}).get("away", 4.5) or 4.5),
            "home_allowed_per_game": float(
                pts_against.get("average", {}).get("home", 4.5) or 4.5),
            "away_allowed_per_game": float(
                pts_against.get("average", {}).get("away", 4.5) or 4.5),
            "win_pct": round(wins / max(games_played, 1), 3),
            "games_played": games_played,
        }
    except Exception:
        return None

def default_stats():
    return {
        "runs_per_game": 4.5,
        "runs_allowed_per_game": 4.5,
        "home_runs_per_game": 4.8,
        "away_runs_per_game": 4.2,
        "home_allowed_per_game": 4.3,
        "away_allowed_per_game": 4.7,
        "win_pct": 0.500,
        "games_played": 0,
    }

def build_features(home_stats, away_stats, league_id, tier, total):
    hs = home_stats or default_stats()
    as_ = away_stats or default_stats()
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

    implied_total = (home_home_rpg + away_away_rpg +
                     away_away_ra + home_home_ra) / 2
    implied_total = max(4.0, min(implied_total, 15.0))

    vegas_line = total if total else league_avg
    total_gap = (implied_total - vegas_line) / 2

    home_str = (home_rpg - home_ra + (home_win_pct - 0.5) * 2)
    away_str = (away_rpg - away_ra + (away_win_pct - 0.5) * 2)
    str_diff = home_str - away_str
    rl_norm = (-1.5 if str_diff > 0 else 1.5) / 2

    month = 6
    fatigue = (1.0 if month <= 6 else
               1.05 if month <= 8 else 1.10)

    return [
        home_rpg, away_rpg,
        home_ra, away_ra,
        home_home_rpg, away_away_rpg,
        home_home_ra, away_away_ra,
        home_win_pct, away_win_pct,
        implied_total, total_gap,
        (home_rpg + away_rpg - 9.0) / 2,
        (home_ra + away_ra - 9.0) / 2,
        home_home_rpg - home_rpg,
        away_away_rpg - away_rpg,
        home_win_pct - away_win_pct,
        str_diff, rl_norm,
        (vegas_line - league_avg) / 2,
        tier_factor, fatigue,
    ]

def train_on_historical():
    from sklearn.linear_model import LogisticRegression
    from sklearn.neural_network import MLPClassifier
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score
    from sklearn.utils.class_weight import compute_class_weight
    from xgboost import XGBClassifier

    print("Building baseball historical dataset...")
    print("Leagues: all tiers | Seasons: 2023-2026 | Weight: 2026=2x\n")

    X, y_total, y_runline, weights = [], [], [], []
    team_stats_cache = {}
    total_games = 0
    total_skipped = 0

    for league_id, league_info in LEAGUE_TIERS.items():
        tier = league_info["tier"]
        league_avg = get_league_avg(league_id)
        league_games = 0

        for season in [2023, 2024, 2025, 2026]:
            season_weight = SEASON_WEIGHTS.get(season, 1.0)
            games = get_season_games(league_id, season)
            if not games:
                continue

            print(f"  Processing {league_info['name']} {season} — "
                  f"{len(games)} games (weight: {season_weight}x)...",
                  flush=True)

            for game in games:
                try:
                    home_id = game["home_id"]
                    away_id = game["away_id"]

                    ht_key = f"{home_id}_{league_id}_{season}"
                    at_key = f"{away_id}_{league_id}_{season}"

                    if ht_key not in team_stats_cache:
                        team_stats_cache[ht_key] = get_team_stats_on_date(
                            home_id, league_id, season)
                    if at_key not in team_stats_cache:
                        team_stats_cache[at_key] = get_team_stats_on_date(
                            away_id, league_id, season)

                    home_stats = team_stats_cache[ht_key]
                    away_stats = team_stats_cache[at_key]

                    features = build_features(
                        home_stats, away_stats,
                        league_id, tier, league_avg)

                    actual_total = game["total"]
                    home_score = game["home_score"]
                    away_score = game["away_score"]
                    goes_over = 1 if actual_total > league_avg else 0
                    home_wins_rl = 1 if (home_score - away_score) > 1.5 else 0

                    X.append(features)
                    y_total.append(goes_over)
                    y_runline.append(home_wins_rl)
                    weights.append(season_weight)
                    total_games += 1
                    league_games += 1

                except Exception:
                    total_skipped += 1
                    continue

        print(f"  {league_info['name']}: {league_games} games processed",
              flush=True)

    print(f"\nTotal dataset: {total_games} games, {total_skipped} skipped")

    if len(X) < 100:
        print("Not enough data — using simulated training")
        from model import train_models
        train_models()
        return False

    X = np.array(X)
    y_total = np.array(y_total)
    y_runline = np.array(y_runline)
    sample_weights = np.array(weights)

    print(f"\nTraining on {len(X)} real games...")
    print("Season weighting: 2026=2x, 2025=1x, 2024=0.75x, 2023=0.5x\n")

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    X_train, X_test, yt_train, yt_test, sw_train, _ = train_test_split(
        X_scaled, y_total, sample_weights,
        test_size=0.2, random_state=42)
    _, _, yr_train, yr_test, _, _ = train_test_split(
        X_scaled, y_runline, sample_weights,
        test_size=0.2, random_state=42)

    total_cw = dict(zip(
        np.unique(yt_train),
        compute_class_weight("balanced",
                             classes=np.unique(yt_train),
                             y=yt_train)))
    rl_cw = dict(zip(
        np.unique(yr_train),
        compute_class_weight("balanced",
                             classes=np.unique(yr_train),
                             y=yr_train)))

    models_total = {}
    models_runline = {}

    print("Training Logistic Regression...")
    lr_t = LogisticRegression(max_iter=2000, C=0.5,
                               class_weight=total_cw, random_state=42)
    lr_t.fit(X_train, yt_train, sample_weight=sw_train)
    models_total["lr"] = lr_t
    print(f"  LR Total: {accuracy_score(yt_test, lr_t.predict(X_test)):.3f}")
    lr_r = LogisticRegression(max_iter=2000, C=0.5,
                               class_weight=rl_cw, random_state=42)
    lr_r.fit(X_train, yr_train, sample_weight=sw_train)
    models_runline["lr"] = lr_r
    print(f"  LR RunLine: {accuracy_score(yr_test, lr_r.predict(X_test)):.3f}")

    print("Training Random Forest...")
    rf_t = RandomForestClassifier(
        n_estimators=200, max_depth=8, min_samples_leaf=20,
        class_weight=total_cw, random_state=42)
    rf_t.fit(X_train, yt_train, sample_weight=sw_train)
    models_total["rf"] = rf_t
    print(f"  RF Total: {accuracy_score(yt_test, rf_t.predict(X_test)):.3f}")
    rf_r = RandomForestClassifier(
        n_estimators=200, max_depth=8, min_samples_leaf=20,
        class_weight=rl_cw, random_state=42)
    rf_r.fit(X_train, yr_train, sample_weight=sw_train)
    models_runline["rf"] = rf_r
    print(f"  RF RunLine: {accuracy_score(yr_test, rf_r.predict(X_test)):.3f}")

    print("Training XGBoost...")
    sps_t = sum(yt_train == 0) / max(sum(yt_train == 1), 1)
    xgb_t = XGBClassifier(
        n_estimators=300, max_depth=5, learning_rate=0.03,
        subsample=0.8, colsample_bytree=0.8,
        scale_pos_weight=sps_t, random_state=42,
        eval_metric="logloss", verbosity=0)
    xgb_t.fit(X_train, yt_train, sample_weight=sw_train)
    models_total["xgb"] = xgb_t
    print(f"  XGB Total: {accuracy_score(yt_test, xgb_t.predict(X_test)):.3f}")
    sps_r = sum(yr_train == 0) / max(sum(yr_train == 1), 1)
    xgb_r = XGBClassifier(
        n_estimators=300, max_depth=5, learning_rate=0.03,
        subsample=0.8, colsample_bytree=0.8,
        scale_pos_weight=sps_r, random_state=42,
        eval_metric="logloss", verbosity=0)
    xgb_r.fit(X_train, yr_train, sample_weight=sw_train)
    models_runline["xgb"] = xgb_r
    print(f"  XGB RunLine: {accuracy_score(yr_test, xgb_r.predict(X_test)):.3f}")

    print("Training Neural Network...")
    nn_t = MLPClassifier(
        hidden_layer_sizes=(64, 32, 16), max_iter=3000,
        learning_rate_init=0.001, early_stopping=True,
        validation_fraction=0.1, random_state=42)
    nn_t.fit(X_train, yt_train)
    models_total["nn"] = nn_t
    print(f"  NN Total: {accuracy_score(yt_test, nn_t.predict(X_test)):.3f}")
    nn_r = MLPClassifier(
        hidden_layer_sizes=(64, 32, 16), max_iter=3000,
        learning_rate_init=0.001, early_stopping=True,
        validation_fraction=0.1, random_state=42)
    nn_r.fit(X_train, yr_train)
    models_runline["nn"] = nn_r
    print(f"  NN RunLine: {accuracy_score(yr_test, nn_r.predict(X_test)):.3f}")

    with open("models.pkl", "wb") as f:
        pickle.dump({
            "models_total": models_total,
            "models_runline": models_runline,
            "scaler": scaler,
            "trained_on": "baseball_all_leagues_2023_2026",
            "games_count": len(X),
        }, f)

    print(f"\n✅ Training complete — {len(X)} real games")
    print("models.pkl saved")
    return True

if __name__ == "__main__":
    train_on_historical()
