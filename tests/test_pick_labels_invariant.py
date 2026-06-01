"""Invariant: pick_labels.GAME_LINE_STATS must be a superset of grade_picks.GAME_LINE_STATS.

If the grader recognises a stat as a game line but the label formatter doesn't,
a legit pick grades cleanly and then renders as a garbled prop line.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))


def test_pick_labels_game_line_stats_is_superset_of_grade_picks():
    from pick_labels import GAME_LINE_STATS as LABEL_STATS
    from grade_picks import GAME_LINE_STATS as GRADE_STATS
    missing = GRADE_STATS - LABEL_STATS
    assert not missing, (
        f"pick_labels.GAME_LINE_STATS is missing stats known to grade_picks: {missing}"
    )
