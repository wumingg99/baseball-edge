import requests
from datetime import datetime, timedelta
import pytz
from config import TIMEZONE

tz = pytz.timezone(TIMEZONE)

# Reuse MLB sheets URL and secret for now
# Can set up separate sheet later
import os
from dotenv import load_dotenv
load_dotenv()
SHEETS_URL = os.getenv("SHEETS_URL", "")
SHEETS_SECRET = os.getenv("SHEETS_SECRET", "")

def log_prediction(game, prediction, odds_entry):
    if not SHEETS_URL or not prediction:
        return
    try:
        today = datetime.now(tz).strftime("%Y-%m-%d")
        game_str = f"{game['away_team']} @ {game['home_team']}"
        total = odds_entry.get("total") if odds_entry else None
        row = [
            today, game_str,
            prediction.get("our_total"),
            total,
            prediction.get("total_gap"),
            prediction.get("total_pred"),
            prediction.get("total_conf"),
            prediction.get("total_votes"),
            prediction.get("rl_pred"),
            prediction.get("rl_conf"),
            prediction.get("rl_votes"),
            prediction.get("rl_edge_flagged"),
            prediction.get("has_data"),
            None, None, None, None, None, None, None
        ]
        payload = {
            "secret": SHEETS_SECRET,
            "action": "log_prediction",
            "sheet": "baseball_predictions",
            "row": row
        }
        requests.post(SHEETS_URL, json=payload, timeout=30)
    except Exception as e:
        print(f"Error logging prediction: {e}")

def get_results_date():
    from datetime import timedelta
    import requests as req
    et_tz = pytz.timezone("America/New_York")
    tz_now = datetime.now(tz)
    et_now = datetime.now(et_tz)
    today_et = et_now.strftime("%Y-%m-%d")
    yesterday_et = (et_now - timedelta(days=1)).strftime("%Y-%m-%d")
    if tz_now.hour < 11:
        return yesterday_et
    try:
        from config import API_BASEBALL_BASE, API_HEADERS, LEAGUE_TIERS
        finals = 0
        for league_id in list(LEAGUE_TIERS.keys())[:5]:
            r = req.get(f"{API_BASEBALL_BASE}/games",
                headers=API_HEADERS,
                params={"league": league_id, "season": et_now.year,
                        "date": today_et},
                timeout=5)
            for g in r.json().get("response", []):
                if g.get("status", {}).get("short") in ["FT", "F"]:
                    finals += 1
        if finals > 0:
            return today_et
        return yesterday_et
    except Exception:
        return yesterday_et

def log_results(date=None):
    if not SHEETS_URL:
        return []
    try:
        from config import API_BASEBALL_BASE, API_HEADERS, LEAGUE_TIERS
        et_tz = pytz.timezone("America/New_York")
        et_now = datetime.now(et_tz)
        target_date = date or get_results_date()
        results = []
        for league_id in LEAGUE_TIERS.keys():
            r = requests.get(f"{API_BASEBALL_BASE}/games",
                headers=API_HEADERS,
                params={"league": league_id,
                        "season": et_now.year,
                        "date": target_date},
                timeout=10)
            for game in r.json().get("response", []):
                if game.get("status", {}).get("short") not in ["FT", "F"]:
                    continue
                home = game["teams"]["home"]["name"]
                away = game["teams"]["away"]["name"]
                scores = game.get("scores", {})
                home_score = scores.get("home", {}).get("total")
                away_score = scores.get("away", {}).get("total")
                if home_score is None or away_score is None:
                    continue
                results.append({
                    "game": f"{away} @ {home}",
                    "home_score": int(home_score),
                    "away_score": int(away_score),
                    "total_result": int(home_score) + int(away_score),
                    "date": target_date,
                })
        return results
    except Exception as e:
        print(f"Error fetching results: {e}")
        return []

def update_results_in_sheet(results, predictions_data=None, date_override=None):
    if not SHEETS_URL:
        return
    results_date = date_override or get_results_date()
    try:
        r = requests.get(SHEETS_URL, params={"sheet": "baseball_predictions"}, timeout=30)
        data = r.json()
        if isinstance(data, dict):
            rows = data.get("rows", [])
        else:
            rows = data
        stored_preds = {}
        for row in rows[1:]:
            if len(row) < 12:
                continue
            try:
                game = str(row[1])
                stored_preds[game] = {
                    "total_pred": str(row[5]),
                    "total_conf": float(row[6] or 0),
                    "rl_pred": str(row[8]),
                    "rl_conf": float(row[9] or 0),
                    "rl_votes": int(row[10] or 0),
                    "edge_flagged": bool(row[11]),
                    "rl_edge_flagged": (float(row[9] or 0) >= 65.0 and
                                        int(row[10] or 0) >= 3),
                    "open_total": float(row[3]) if row[3] else None,
                    "league_avg": 7.5,
                }
            except Exception:
                continue
    except Exception as e:
        print(f"Error reading predictions: {e}")
        stored_preds = {}

    for result in results:
        pred = None
        for game_key, p in stored_preds.items():
            if (result["game"] in game_key or
                    game_key in result["game"]):
                pred = p
                break
        if not pred:
            continue
        if not (pred.get("edge_flagged") or pred.get("rl_edge_flagged")):
            continue
        home_score = result["home_score"]
        away_score = result["away_score"]
        total_result = result["total_result"]
        open_total = pred.get("open_total") or pred.get("league_avg", 7.5)
        ou_result = "OVER" if total_result > open_total else "UNDER"
        ou_correct = "✅" if pred.get("total_pred") == ou_result else "❌"
        rl_pred = pred.get("rl_pred", "")
        home_margin = home_score - away_score
        if rl_pred in ["HOME -1.5"]:
            rl_correct = "✅" if home_margin > 1.5 else "❌"
        elif rl_pred in ["HOME +1.5"]:
            rl_correct = "✅" if home_margin >= -1.5 else "❌"
        elif rl_pred in ["AWAY +1.5"]:
            rl_correct = "✅" if home_margin <= 1.5 else "❌"
        else:
            rl_correct = "✅" if home_margin < -1.5 else "❌"
        try:
            payload = {
                "secret": SHEETS_SECRET,
                "action": "log_result",
                "sheet": "baseball_predictions",
                "date": results_date,
                "game": result["game"],
                "home_score": home_score,
                "away_score": away_score,
                "total_result": total_result,
                "ou_result": ou_result,
                "ou_correct": ou_correct,
                "rl_result": rl_pred,
                "rl_correct": rl_correct,
                "correct": rl_correct
            }
            r = requests.post(SHEETS_URL, json=payload, timeout=30)
            print(f"Result: {result['game']} | "
                  f"RL: {rl_pred} {rl_correct} | "
                  f"O/U: {ou_result} {ou_correct}")
        except Exception as e:
            print(f"Error updating result: {e}")

def get_record():
    if not SHEETS_URL:
        return None
    try:
        response = requests.get(SHEETS_URL, params={"sheet": "baseball_predictions"}, timeout=30)
        data = response.json()
        if isinstance(data, dict):
            rows = data.get("rows", [])
        else:
            rows = data
        if len(rows) <= 1:
            return None
        rl_total = rl_correct_count = 0
        ou_total = ou_correct_count = 0
        rl_flagged_total = rl_flagged_correct = 0
        ou_flagged_total = ou_flagged_correct = 0
        monthly = {}
        for row in rows[1:]:
            if len(row) < 19:
                continue
            date = str(row[0])[:7]
            rl_corr = str(row[19]) if len(row) > 19 else ""
            ou_corr = str(row[17]) if len(row) > 17 else ""
            is_rl_flagged = (float(row[9] or 0) >= 65.0 and
                             int(row[10] or 0) >= 3)
            is_ou_flagged = (str(row[11]) == "True" or
                             row[11] is True)
            if rl_corr in ["✅", "❌"]:
                rl_total += 1
                if rl_corr == "✅":
                    rl_correct_count += 1
                if is_rl_flagged:
                    rl_flagged_total += 1
                    if rl_corr == "✅":
                        rl_flagged_correct += 1
            if ou_corr in ["✅", "❌"]:
                ou_total += 1
                if ou_corr == "✅":
                    ou_correct_count += 1
                if is_ou_flagged:
                    ou_flagged_total += 1
                    if ou_corr == "✅":
                        ou_flagged_correct += 1
            if date not in monthly:
                monthly[date] = {
                    "rl": 0, "rl_correct": 0,
                    "ou": 0, "ou_correct": 0
                }
            if rl_corr in ["✅", "❌"] and is_rl_flagged:
                monthly[date]["rl"] += 1
                if rl_corr == "✅":
                    monthly[date]["rl_correct"] += 1
            if ou_corr in ["✅", "❌"] and is_ou_flagged:
                monthly[date]["ou"] += 1
                if ou_corr == "✅":
                    monthly[date]["ou_correct"] += 1
        return {
            "rl_total": rl_total,
            "rl_correct": rl_correct_count,
            "rl_accuracy": round(
                rl_correct_count / rl_total * 100, 1) if rl_total > 0 else 0,
            "ou_total": ou_total,
            "ou_correct": ou_correct_count,
            "ou_accuracy": round(
                ou_correct_count / ou_total * 100, 1) if ou_total > 0 else 0,
            "rl_flagged_total": rl_flagged_total,
            "rl_flagged_correct": rl_flagged_correct,
            "rl_flagged_accuracy": round(
                rl_flagged_correct / rl_flagged_total * 100, 1
            ) if rl_flagged_total > 0 else 0,
            "ou_flagged_total": ou_flagged_total,
            "ou_flagged_correct": ou_flagged_correct,
            "ou_flagged_accuracy": round(
                ou_flagged_correct / ou_flagged_total * 100, 1
            ) if ou_flagged_total > 0 else 0,
            "total": rl_total + ou_total,
            "monthly": monthly
        }
    except Exception as e:
        print(f"Error getting record: {e}")
        return None
