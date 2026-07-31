"""Tests for the pure scoring engine."""

import pytest

from app.scoring import (
    Track, score_entry, compute_standing, build_leaderboard,
    QUALIFYING_SCORE,
)


def test_base_activity_points():
    assert score_entry("course").points == 10
    assert score_entry("certification").points == 25
    assert score_entry("use_case_submitted").points == 40


def test_measured_impact_bonus_applies_only_to_demoed_poc():
    assert score_entry("poc_demoed", impact_measured=True).points == 110
    assert score_entry("poc_demoed", impact_measured=False).points == 60
    # bonus must not leak onto other activities
    assert score_entry("course", impact_measured=True).points == 10


def test_scalability_bonus():
    assert score_entry("use_case_submitted", highly_scalable=True).points == 80
    assert score_entry("use_case_submitted", highly_scalable=False).points == 40


def test_unknown_activity_raises():
    with pytest.raises(ValueError):
        score_entry("nap")


def test_track_is_derived_not_trusted():
    assert score_entry("certification").track == Track.FLUENCY
    assert score_entry("poc_demoed").track == Track.POC
    assert score_entry("reusable_component").track == Track.USE_CASE


def test_fluency_cap_limits_contribution_to_25pct():
    # All fluency, no other tracks -> capped to 0 (can't exceed 25% of total)
    entries = [score_entry("certification") for _ in range(10)]  # 250 raw
    standing = compute_standing(entries)
    assert standing.fluency_points_raw == 250
    assert standing.fluency_points_counted == 0
    assert standing.total_points == 0


def test_fluency_cap_with_other_points():
    # 90 points of POC work; fluency should be capped at 90/3 = 30
    entries = [
        score_entry("poc_demoed"),        # 60, POC
        score_entry("poc_chartered"),     # 30, POC
        score_entry("certification"),     # 25, fluency
        score_entry("certification"),     # 25, fluency  (50 raw fluency)
    ]
    standing = compute_standing(entries)
    assert standing.fluency_points_raw == 50
    assert standing.fluency_points_counted == 30   # capped
    assert standing.total_points == 120            # 90 + 30


def test_qualification_requires_score_and_all_three_tracks():
    # Enough points but only two tracks -> not qualified
    entries = [
        score_entry("poc_demoed", impact_measured=True),  # 110 POC
        score_entry("poc_adopted"),                        # 60 POC
        score_entry("reusable_component"),                 # 50 use case
        score_entry("use_case_submitted", highly_scalable=True),  # 80 use case
    ]
    standing = compute_standing(entries)
    assert standing.total_points >= QUALIFYING_SCORE
    assert standing.tracks_covered == 2
    assert standing.qualified is False


def test_full_qualification():
    entries = [
        score_entry("poc_demoed", impact_measured=True),  # 110 POC
        score_entry("poc_adopted"),                        # 60 POC
        score_entry("use_case_submitted", highly_scalable=True),  # 80 use case
        score_entry("certification"),                      # 25 fluency (capped)
    ]
    standing = compute_standing(entries)
    assert standing.tracks_covered == 3
    assert standing.qualified is True


def test_points_to_cut_never_negative():
    entries = [score_entry("poc_demoed", impact_measured=True)]
    standing = compute_standing(entries)
    assert standing.points_to_cut == QUALIFYING_SCORE - 110


def test_leaderboard_ranks_and_gaps():
    board = build_leaderboard({
        "Alice": [score_entry("poc_demoed", impact_measured=True)],  # 110
        "Bob": [score_entry("poc_demoed")],                          # 60
        "Cara": [score_entry("course")],                             # 0 (fluency capped)
    })
    assert [r["name"] for r in board] == ["Alice", "Bob", "Cara"]
    assert board[0]["rank"] == 1
    assert board[0]["gap_to_above"] == 0
    assert board[1]["gap_to_above"] == 50   # 110 - 60


def test_leaderboard_tie_breaks_alphabetically():
    board = build_leaderboard({
        "Zoe": [score_entry("poc_demoed")],   # 60
        "Ada": [score_entry("poc_demoed")],   # 60
    })
    assert [r["name"] for r in board] == ["Ada", "Zoe"]
