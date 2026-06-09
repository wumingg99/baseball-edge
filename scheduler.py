from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from datetime import datetime

tz = pytz.timezone("Asia/Singapore")

async def scheduled_brief(app):
    try:
        from bot import send_message, fetch_all_games, format_summary
        from config import ODDS_API_KEY
        now = datetime.now(tz).strftime("%b %d, %Y")
        games, games_data = await fetch_all_games(ODDS_API_KEY)
        if not games_data:
            await send_message(app,
                f"⚾ Baseball Edge — {now}\n\nNo games today.")
            return
        edge_count = sum(1 for _, p, _ in games_data
                         if p and (p.get("edge_flagged") or
                                   p.get("rl_edge_flagged")))
        if edge_count > 0:
            summary = format_summary(games_data, now)
            await send_message(app, summary)
        else:
            await send_message(app,
                f"⚾ Baseball Edge — {now}\n\n"
                f"{len(games_data)} games — no edges flagged.")
    except Exception as e:
        import traceback
        print(f"Brief error: {e}\n{traceback.format_exc()}", flush=True)

async def check_new_lines(app):
    try:
        from bot import send_message, fetch_all_games, _notified_games
        from config import ODDS_API_KEY
        games, games_data = await fetch_all_games(ODDS_API_KEY)
        if not games_data:
            return
        new_edges = []
        for game, pred, odds in games_data:
            game_id = str(game.get("game_id"))
            if game_id in _notified_games:
                continue
            if pred and (pred.get("edge_flagged") or
                         pred.get("rl_edge_flagged")):
                _notified_games.add(game_id)
                new_edges.append((game, pred, odds))
        if new_edges:
            now = datetime.now(tz).strftime("%b %d, %Y")
            msg = f"🆕 New Baseball Edges — {now}\n"
            msg += f"{len(new_edges)} new edge(s)\n━━━━━━━━━━━━━━━━━━━━\n"
            for game, pred, odds in new_edges:
                total = odds.get("total") if odds else "N/A"
                msg += (f"⚾ {game['away_team']} @ {game['home_team']}"
                        f" ({game['league_name']})\n"
                        f"   O/U: {total} | RL: {pred.get('rl_pred')}"
                        f" {pred.get('rl_conf')}%\n")
            msg += "\nRun /baseball_brief for predictions"
            await send_message(app, msg)
    except Exception as e:
        print(f"New lines error: {e}", flush=True)

async def pregame_alerts(app):
    try:
        from bot import send_message, fetch_all_games
        from config import ODDS_API_KEY
        now = datetime.now(tz)
        games, games_data = await fetch_all_games(ODDS_API_KEY)
        for game, pred, odds in games_data:
            if not pred:
                continue
            if not (pred.get("edge_flagged") or pred.get("rl_edge_flagged")):
                continue
            start = game.get("start_time_sgt", "")
            if not start:
                continue
            try:
                game_dt = datetime.fromisoformat(start)
                game_dt = tz.localize(game_dt)
                mins = (game_dt - now).total_seconds() / 60
                if 55 <= mins <= 75:
                    total = odds.get("total") if odds else "N/A"
                    start_str = game_dt.strftime("%I:%M %p SGT")
                    msg = (f"⏰ Starting at {start_str}\n"
                           f"⚾ {game['away_team']} @ {game['home_team']}\n"
                           f"🏆 {game['league_name']} — {game['country']}\n"
                           f"━━━━━━━━━━━━━━━━━━━━\n"
                           f"O/U: {pred['total_pred']} {total} — "
                           f"{pred['total_conf']}%\n"
                           f"RL: {pred['rl_pred']} — "
                           f"{pred['rl_conf']}%\n"
                           f"Win: Home {pred['home_win_prob']*100:.0f}% / "
                           f"Away {pred['away_win_prob']*100:.0f}%\n"
                           f"━━━━━━━━━━━━━━━━━━━━\n"
                           f"Last chance to act on this edge")
                    await send_message(app, msg)
            except Exception:
                continue
    except Exception as e:
        print(f"Pregame alerts error: {e}", flush=True)

async def evening_results(app):
    try:
        from bot import send_message, fetch_all_games
        from sheets import log_results, update_results_in_sheet
        from config import ODDS_API_KEY
        now = datetime.now(tz).strftime("%b %d, %Y")
        results = log_results()
        if not results:
            return
        _, games_data = await fetch_all_games(ODDS_API_KEY)
        update_results_in_sheet(results, games_data)
        flagged = [(r, next((p for g, p, o in games_data
                    if p and f"{g['away_team']} @ {g['home_team']}" == r["game"]),
                    None))
                   for r in results]
        flagged = [(r, p) for r, p in flagged
                   if p and (p.get("edge_flagged") or p.get("rl_edge_flagged"))]
        if not flagged:
            return
        correct = sum(1 for r, p in flagged
                      if p.get("rl_pred", "").startswith("HOME") and
                      r["home_score"] - r["away_score"] > 1.5 or
                      p.get("rl_pred", "").startswith("AWAY") and
                      r["home_score"] - r["away_score"] <= 1.5)
        msg = f"🌙 Baseball Results — {now}\n━━━━━━━━━━━━━━━━━━━━\n"
        for r, p in flagged:
            rl_pred = p.get("rl_pred", "")
            margin = r["home_score"] - r["away_score"]
            if rl_pred in ["HOME -1.5", "HOME +1.5"]:
                rl_ok = margin > 1.5 if rl_pred == "HOME -1.5" else margin >= -1.5
            else:
                rl_ok = margin <= 1.5 if rl_pred == "AWAY +1.5" else margin < -1.5
            emoji = "✅" if rl_ok else "❌"
            msg += (f"{emoji} {r['game']}\n"
                    f"   {r['away_score']}-{r['home_score']} | "
                    f"RL: {rl_pred}\n")
        msg += (f"━━━━━━━━━━━━━━━━━━━━\n"
                f"RL: {correct}/{len(flagged)} correct\n"
                f"Run /baseball_record for full stats")
        await send_message(app, msg)
    except Exception as e:
        print(f"Evening results error: {e}", flush=True)

async def nightly_retrain(app):
    try:
        from bot import send_message
        import os
        if os.path.exists("models.pkl"):
            mtime_age = (datetime.now(tz).timestamp() -
                         os.path.getmtime("models.pkl")) / 86400
            if mtime_age > 7:
                from historical import train_on_historical
                train_on_historical()
                await send_message(app, "🧠 Baseball model retrained")
    except Exception as e:
        print(f"Retrain error: {e}", flush=True)

def setup_scheduler(app):
    scheduler = AsyncIOScheduler(timezone=tz)

    # New lines every 3 hours
    for hour in [0, 3, 6, 9, 12, 15, 18, 21]:
        scheduler.add_job(check_new_lines, CronTrigger(
            hour=hour, minute=0, timezone=tz),
            args=[app], id=f"new_lines_{hour}",
            name=f"New Lines {hour}:00")

    # Daily briefs
    for hour, name in [(23, "11PM"), (1, "1AM"),
                       (6, "6AM"), (10, "10AM")]:
        scheduler.add_job(scheduled_brief, CronTrigger(
            hour=hour, minute=0, timezone=tz),
            args=[app], id=f"brief_{hour}",
            name=f"Brief {name}")

    # Pregame alerts every 15 mins
    for minute in [0, 15, 30, 45]:
        scheduler.add_job(pregame_alerts, CronTrigger(
            minute=minute, timezone=tz),
            args=[app], id=f"pregame_{minute}",
            name=f"Pregame :{minute:02d}")

    # Evening results 8PM SGT
    scheduler.add_job(evening_results, CronTrigger(
        hour=20, minute=0, timezone=tz),
        args=[app], id="evening_results",
        name="Evening Results 8PM")

    # Nightly retrain 2:30AM SGT
    scheduler.add_job(nightly_retrain, CronTrigger(
        hour=2, minute=30, timezone=tz),
        args=[app], id="nightly_retrain",
        name="Nightly Retrain")

    return scheduler
