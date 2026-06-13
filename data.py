import requests
from datetime import datetime, timedelta
import pytz
from config import API_BASEBALL_BASE, API_HEADERS, TIMEZONE, LEAGUE_TIERS, ODDS_API_KEY

_cache = {}
_games_data_cache = []

def get_todays_games():
    tz = pytz.timezone(TIMEZONE)
    et_tz = pytz.timezone("America/New_York")
    sgt_now = datetime.now(tz)
    et_now = datetime.now(et_tz)
    from datetime import timedelta
    if et_now.hour >= 23:
        today = (et_now + timedelta(days=1)).strftime("%Y-%m-%d")
        _cache["showing_next_day"] = True
    else:
        today = et_now.strftime("%Y-%m-%d")
        _cache["showing_next_day"] = False
    if "games" in _cache and _cache.get("games_date") == today:
        return _cache["games"]
    games = []
    for league_id, league_info in LEAGUE_TIERS.items():
        try:
            url = f"{API_BASEBALL_BASE}/games"
            params = {
                "league": league_id,
                "season": et_now.year,
                "date": today
            }
            r = requests.get(url, headers=API_HEADERS, params=params, timeout=10)
            if r.status_code != 200:
                continue
            data = r.json()
            for game in data.get("response", []):
                status = game.get("status", {}).get("long", "")
                if status in ["Postponed", "Cancelled"]:
                    continue
                home = game.get("teams", {}).get("home", {})
                away = game.get("teams", {}).get("away", {})
                date_str = game.get("date", "")
                game_time_sgt = ""
                if date_str:
                    try:
                        from datetime import timezone
                        utc_dt = datetime.fromisoformat(
                            date_str.replace("Z", "+00:00"))
                        sgt_dt = utc_dt.astimezone(tz)
                        game_time_sgt = sgt_dt.strftime("%Y-%m-%dT%H:%M:%S")
                    except Exception:
                        pass
                home_score = game.get("scores", {}).get("home", {}).get("total")
                away_score = game.get("scores", {}).get("away", {}).get("total")
                games.append({
                    "game_id": game.get("id"),
                    "date": today,
                    "league_id": league_id,
                    "league_name": league_info["name"],
                    "league_tier": league_info["tier"],
                    "country": league_info["country"],
                    "home_team": home.get("name", "Unknown"),
                    "away_team": away.get("name", "Unknown"),
                    "home_id": home.get("id"),
                    "away_id": away.get("id"),
                    "status": status,
                    "start_time_sgt": game_time_sgt,
                    "home_score": home_score,
                    "away_score": away_score,
                })
        except Exception as e:
            print(f"Error fetching league {league_id}: {e}")
            continue
    # Deduplicate by game_id
    seen = set()
    unique_games = []
    for g in games:
        gid = g.get("game_id")
        if gid not in seen:
            seen.add(gid)
            unique_games.append(g)
    games = unique_games
    print(f"Fetched {len(games)} games today across {len(LEAGUE_TIERS)} leagues")
    _cache["games"] = games
    _cache["games_date"] = today
    return games

def get_team_stats(team_id, league_id, season=None):
    if not team_id:
        return _default_team_stats()
    cache_key = f"team_{team_id}_{league_id}"
    if cache_key in _cache:
        return _cache[cache_key]
    result = _default_team_stats()
    try:
        et_tz = pytz.timezone("America/New_York")
        season = season or datetime.now(et_tz).year
        url = f"{API_BASEBALL_BASE}/teams/statistics"
        params = {"league": league_id, "season": season, "team": team_id}
        r = requests.get(url, headers=API_HEADERS, params=params, timeout=5)
        if r.status_code != 200:
            return result
        data = r.json().get("response", {})
        if not data:
            return result
        games = data.get("games", {})
        points = data.get("points", {})
        wins_all = games.get("wins", {}).get("all", {})
        loses_all = games.get("loses", {}).get("all", {})
        games_played = games.get("played", {}).get("all", 1) or 1
        wins = int(wins_all.get("total", 0) or 0)
        losses = int(loses_all.get("total", 0) or 0)
        pts_for = points.get("for", {})
        pts_against = points.get("against", {})
        from model import get_league_avg
        league_avg = get_league_avg(league_id)
        league_avg_per_team = league_avg / 2  # split total into per-team runs

        # Empirical Bayes shrinkage — pulls small-sample teams toward
        # league average. K=15 means a team needs ~15 games before
        # its own stats dominate the estimate.
        K = 15

        def shrink(raw_value, default=league_avg_per_team):
            return (games_played * raw_value + K * default) / (games_played + K)

        raw_rpg = float(pts_for.get("average", {}).get("all", 4.5) or 4.5)
        raw_rapg = float(pts_against.get("average", {}).get("all", 4.5) or 4.5)
        raw_home_rpg = float(pts_for.get("average", {}).get("home", 4.5) or 4.5)
        raw_away_rpg = float(pts_for.get("average", {}).get("away", 4.5) or 4.5)
        raw_home_allowed = float(pts_against.get("average", {}).get("home", 4.5) or 4.5)
        raw_away_allowed = float(pts_against.get("average", {}).get("away", 4.5) or 4.5)
        raw_win_pct = wins / max(games_played, 1)

        result = {
            "runs_per_game": round(shrink(raw_rpg), 3),
            "runs_allowed_per_game": round(shrink(raw_rapg), 3),
            "home_runs_per_game": round(shrink(raw_home_rpg), 3),
            "away_runs_per_game": round(shrink(raw_away_rpg), 3),
            "home_allowed_per_game": round(shrink(raw_home_allowed), 3),
            "away_allowed_per_game": round(shrink(raw_away_allowed), 3),
            "win_pct": round(shrink(raw_win_pct, default=0.5), 3),
            "games_played": games_played,
            "data_confidence": round(min(games_played / (games_played + K), 1.0), 3),
        }
    except Exception as e:
        print(f"Team stats error {team_id}: {e}")
    _cache[cache_key] = result
    return result

def _default_team_stats():
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

def get_odds(api_key):
    if "odds" in _cache:
        return _cache["odds"]
    odds = []
    sport_keys = ["baseball_kbo", "baseball_npb"]
    for sport_key in sport_keys:
        try:
            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
            params = {
                "apiKey": api_key,
                "regions": "us",
                "markets": "totals,spreads",
                "oddsFormat": "american",
            }
            r = requests.get(url, params=params, timeout=10)
            data = r.json()
            if not isinstance(data, list):
                print(f"Odds error for {sport_key}: {data}")
                continue
            for game in data:
                entry = {
                    "home_team": game.get("home_team"),
                    "away_team": game.get("away_team"),
                    "total": None,
                    "run_line": None,
                    "sport_key": sport_key,
                }
                for bookmaker in game.get("bookmakers", [])[:1]:
                    for market in bookmaker.get("markets", []):
                        if market["key"] == "totals":
                            for outcome in market["outcomes"]:
                                if outcome["name"] == "Over":
                                    entry["total"] = outcome["point"]
                        if market["key"] == "spreads":
                            for outcome in market["outcomes"]:
                                if outcome["name"] == game["home_team"]:
                                    entry["run_line"] = outcome["point"]
                odds.append(entry)
        except Exception as e:
            print(f"Odds error for {sport_key}: {e}")
    _cache["odds"] = odds
    return odds

def build_game_context(game):
    league_id = game.get("league_id")
    home_stats = get_team_stats(game.get("home_id"), league_id)
    away_stats = get_team_stats(game.get("away_id"), league_id)
    tier = game.get("league_tier", 2)
    return {
        "home_stats": home_stats,
        "away_stats": away_stats,
        "league_tier": tier,
        "league_id": league_id,
        "league_name": game.get("league_name"),
    }

def clear_cache():
    global _games_data_cache
    _cache.clear()
    _games_data_cache = []

def preload_all_data(api_key):
    global _games_data_cache
    print("Preloading baseball game data...")
    games = get_todays_games()
    if not games:
        print("No games today")
        return []
    odds_list = get_odds(api_key)
    games_data = []
    for game in games:
        print(f"Loading: {game['away_team']} @ {game['home_team']} ({game['league_name']})")
        context = build_game_context(game)
        odds_entry = next((
            o for o in odds_list
            if game["home_team"].lower()[:8] in (o.get("home_team") or "").lower() or
            game["away_team"].lower()[:8] in (o.get("away_team") or "").lower()
        ), None)
        games_data.append((game, context, odds_entry))
    _games_data_cache = games_data
    print(f"Preloaded {len(games_data)} games")
    return games_data

def get_cached_games_data():
    return _games_data_cache
