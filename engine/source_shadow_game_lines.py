"""source_shadow_game_lines.py -- EdgeModel-vs-live shadow for MLB game lines.

The game-line analogue of source_shadow.py: for graded MLB game-line bets in
pick_log_game_lines.csv (priced live by analyze_game_lines from the SaberSim feed),
look up EdgeModel's starter-aware game-line projection (mlb_game_projections, which
is otherwise orphaned) for the same game, derive the actual outcome from the logged
(direction, result), and record which source implied the right side. This finally
tests the starter-aware model on real outcomes.

Covers full-game TOTAL and MONEYLINE (the direct mlb_game_projections fields:
proj_total, p_home_win). SPREAD / TEAM_TOTAL / F5_* are extensions.

Match key: (game_date, home_abbr, away_abbr). Post-hoc, read-only, fail-soft.
Writes data/pick_log_gl_source_compare.csv. Run after grading.
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

_ENGINE = Path(__file__).resolve().parent
if str(_ENGINE) not in sys.path:
    sys.path.insert(0, str(_ENGINE))

from secrets_config import EDGEMODEL_DB_PATH

try:
    from paths import PICK_LOG_GAME_LINES_PATH, DATA_DIR
except Exception:  # pragma: no cover
    DATA_DIR = _ENGINE.parent / "data"
    PICK_LOG_GAME_LINES_PATH = DATA_DIR / "pick_log_game_lines.csv"

_OUT_PATH = Path(DATA_DIR) / "pick_log_gl_source_compare.csv"
_OUT_FIELDS = ["date", "game", "market", "line", "live_side", "em_side",
               "actual", "live_win", "em_win", "agree", "disagree_winner",
               # #9: proper scoring -- each source's prob for the binary event
               # (over / home-win) + Brier vs outcome, so the readiness gate's
               # Brier veto applies to game-line markets too.
               "live_prob", "em_prob", "live_brier", "em_brier"]


def _brier(p, outcome: int):
    """(p-outcome)^2, or '' if p isn't a usable probability."""
    try:
        p = float(p)
    except (TypeError, ValueError):
        return ""
    if not 0.0 <= p <= 1.0:
        return ""
    return round((p - outcome) ** 2, 6)


def _live_prob_for_event(win_prob, bet_dir: str, event_dir: str):
    """Live source's probability of `event_dir` from the logged win_prob (the prob of
    the bet's own side). e.g. a logged 'under' win_prob -> P(over) = 1 - win_prob."""
    try:
        wp = float(win_prob)
    except (TypeError, ValueError):
        return ""
    if not 0.0 <= wp <= 1.0:
        return ""
    return round(wp if bet_dir == event_dir else 1.0 - wp, 6)


def fetch_mlb_game_projections(game_date: str, db_path=None) -> dict:
    """{(HOME_ABBR, AWAY_ABBR): {proj_total, p_home_win, ...}} for a date. {} on failure."""
    path = Path(db_path or EDGEMODEL_DB_PATH)
    if not path.exists():
        return {}
    out: dict = {}
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT home_abbr, away_abbr, proj_total, proj_spread, p_home_win, "
                "p_over_total, proj_f5_total FROM mlb_game_projections WHERE run_date = ?",
                (game_date,)).fetchall()
        except sqlite3.OperationalError:
            return {}
        for r in rows:
            out[((r["home_abbr"] or "").upper(), (r["away_abbr"] or "").upper())] = dict(r)
        conn.close()
    except Exception:
        return {}
    return out


def _teams(game: str) -> tuple:
    """'AWAY@HOME' -> (HOME, AWAY) upper."""
    if "@" not in (game or ""):
        return "", ""
    away, home = game.split("@", 1)
    return home.strip().upper(), away.strip().upper()


def compare_rows(pick_rows: list[dict], fetch=fetch_mlb_game_projections, db_path=None) -> list[dict]:
    """Join graded MLB game-line bets to EdgeModel game projections; return comparison rows."""
    by_date: dict = defaultdict(list)
    for r in pick_rows:
        if (r.get("sport") or "").upper() == "MLB" and r.get("date"):
            by_date[r["date"]].append(r)

    out: list[dict] = []
    for date, rows in by_date.items():
        proj = fetch(date, db_path=db_path)
        if not proj:
            continue
        for r in rows:
            result = (r.get("result") or "").strip().upper()
            if result not in ("W", "L"):
                continue
            market = (r.get("stat") or "").strip().upper()
            home, away = _teams(r.get("game", ""))
            g = proj.get((home, away))
            if not g:
                continue
            direction = (r.get("direction") or "").strip().lower()

            # event_dir = the canonical binary event we score both sources on.
            if market == "TOTAL" and direction in ("over", "under"):
                try:
                    line = float(r.get("line"))
                except (TypeError, ValueError):
                    continue
                if g.get("proj_total") is None:
                    continue
                actual_over = (direction == "over") == (result == "W")
                live_side = direction
                em_side = "over" if g["proj_total"] > line else "under"
                actual = "over" if actual_over else "under"
                event_dir, outcome = "over", int(actual_over)
                em_prob = g.get("p_over_total")
            elif market == "ML" and direction in ("home", "away"):
                if g.get("p_home_win") is None:
                    continue
                actual_home = (direction == "home") == (result == "W")
                live_side = direction
                em_side = "home" if g["p_home_win"] > 0.5 else "away"
                actual = "home" if actual_home else "away"
                event_dir, outcome = "home", int(actual_home)
                em_prob = g.get("p_home_win")
            else:
                continue  # SPREAD / TEAM_TOTAL / F5_* not covered yet

            live_win = result == "W"
            em_win = em_side == actual
            agree = live_side == em_side
            live_prob = _live_prob_for_event(r.get("win_prob"), direction, event_dir)
            out.append({
                "date": date, "game": r.get("game", ""), "market": market,
                "line": r.get("line", ""), "live_side": live_side, "em_side": em_side,
                "actual": actual, "live_win": int(live_win), "em_win": int(em_win),
                "agree": int(agree),
                "disagree_winner": "" if agree else ("edgemodel" if em_win else "live"),
                "live_prob": live_prob, "em_prob": em_prob if em_prob is not None else "",
                "live_brier": _brier(live_prob, outcome),
                "em_brier": _brier(em_prob, outcome),
            })
    return out


def run(pick_log_path=None, db_path=None, out_path=None) -> list[dict]:
    path = Path(pick_log_path or PICK_LOG_GAME_LINES_PATH)
    rows = list(csv.DictReader(open(path, encoding="utf-8"))) if path.exists() else []
    comp = compare_rows(rows, db_path=db_path)
    out = Path(out_path or _OUT_PATH)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_OUT_FIELDS)
        w.writeheader()
        w.writerows(comp)
    return comp


if __name__ == "__main__":
    argparse.ArgumentParser(description="EdgeModel-vs-live MLB game-line shadow").parse_args()
    comp = run()
    n_dis = sum(1 for r in comp if not r["agree"])
    em_dis = sum(1 for r in comp if r["disagree_winner"] == "edgemodel")
    print(f"MLB game-line comparison: {len(comp)} graded bets with an EdgeModel projection")
    print(f"  disagreements: {n_dis}; EdgeModel won {em_dis} -> {_OUT_PATH}")
