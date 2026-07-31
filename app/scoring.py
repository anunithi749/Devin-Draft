"""Scoring engine for The Devin Draft.

Pure functions with no framework or database dependencies so the rules can be
unit-tested in isolation and reused anywhere. Everything the rest of the app
knows about how points work lives here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Track(str, Enum):
    FLUENCY = "AI Fluency"
    POC = "AI POC"
    USE_CASE = "Devin Use Case"


# Base points per activity. The activity's track is derived from this table so
# a submission can never claim points under the wrong track.
ACTIVITY_POINTS: dict[str, int] = {
    # AI Fluency
    "course": 10,
    "certification": 25,
    "taught_session": 20,
    "learning_plan": 15,
    "prompt_published": 15,
    # AI POC
    "poc_chartered": 30,
    "poc_demoed": 60,
    "poc_adopted": 60,
    # Devin Use Case
    "use_case_submitted": 40,
    "reusable_component": 50,
}

ACTIVITY_TRACK: dict[str, Track] = {
    "course": Track.FLUENCY,
    "certification": Track.FLUENCY,
    "taught_session": Track.FLUENCY,
    "learning_plan": Track.FLUENCY,
    "prompt_published": Track.FLUENCY,
    "poc_chartered": Track.POC,
    "poc_demoed": Track.POC,
    "poc_adopted": Track.POC,
    "use_case_submitted": Track.USE_CASE,
    "reusable_component": Track.USE_CASE,
}

# Bonus points for structurally meaningful attributes.
MEASURED_IMPACT_BONUS = 50   # a demoed POC with a real before/after metric
HIGH_SCALABILITY_BONUS = 40  # a use case the panel rates highly scalable

# Program-level constants.
QUALIFYING_SCORE = 250
FLUENCY_CAP_FRACTION = 0.25  # AI Fluency may supply at most 25% of the total


@dataclass(frozen=True)
class ScoredEntry:
    """A single submission's contribution, after bonuses."""
    activity_type: str
    track: Track
    points: int


def score_entry(activity_type: str, *, impact_measured: bool = False,
                highly_scalable: bool = False) -> ScoredEntry:
    """Score one submission, including attribute bonuses.

    Raises ValueError on an unknown activity type so bad data fails loudly
    rather than silently scoring zero.
    """
    if activity_type not in ACTIVITY_POINTS:
        raise ValueError(f"Unknown activity type: {activity_type!r}")

    points = ACTIVITY_POINTS[activity_type]
    track = ACTIVITY_TRACK[activity_type]

    if activity_type == "poc_demoed" and impact_measured:
        points += MEASURED_IMPACT_BONUS
    if activity_type == "use_case_submitted" and highly_scalable:
        points += HIGH_SCALABILITY_BONUS

    return ScoredEntry(activity_type=activity_type, track=track, points=points)


def _apply_fluency_cap(fluency: int, other: int) -> int:
    """Cap AI Fluency so it supplies at most FLUENCY_CAP_FRACTION of the total.

    Solving fluency_allowed <= f * (fluency_allowed + other):
        fluency_allowed <= (f / (1 - f)) * other
    With f = 0.25 that is fluency_allowed <= other / 3.
    """
    if fluency <= 0:
        return 0
    ratio = FLUENCY_CAP_FRACTION / (1 - FLUENCY_CAP_FRACTION)
    allowed = int(other * ratio)
    return min(fluency, allowed)


@dataclass(frozen=True)
class Standing:
    """A participant's computed position in the draft."""
    total_points: int
    tracks_covered: int
    fluency_points_raw: int
    fluency_points_counted: int
    qualified: bool
    points_to_cut: int


def compute_standing(entries: list[ScoredEntry]) -> Standing:
    """Aggregate one participant's approved entries into a standing.

    Applies the fluency cap and the qualification gate (>= QUALIFYING_SCORE
    AND at least one entry in all three tracks).
    """
    fluency_raw = sum(e.points for e in entries if e.track == Track.FLUENCY)
    other = sum(e.points for e in entries if e.track != Track.FLUENCY)

    fluency_counted = _apply_fluency_cap(fluency_raw, other)
    total = fluency_counted + other

    tracks_covered = len({e.track for e in entries})
    qualified = total >= QUALIFYING_SCORE and tracks_covered == len(Track)
    points_to_cut = max(0, QUALIFYING_SCORE - total)

    return Standing(
        total_points=total,
        tracks_covered=tracks_covered,
        fluency_points_raw=fluency_raw,
        fluency_points_counted=fluency_counted,
        qualified=qualified,
        points_to_cut=points_to_cut,
    )


def build_leaderboard(participants: dict[str, list[ScoredEntry]]) -> list[dict]:
    """Turn {name: [entries]} into a ranked leaderboard.

    Ties break alphabetically so ordering is stable and reproducible.
    Includes the near-miss gap to the person one rank above — the FOMO hook.
    """
    rows = []
    for name, entries in participants.items():
        standing = compute_standing(entries)
        rows.append({
            "name": name,
            "total_points": standing.total_points,
            "tracks_covered": standing.tracks_covered,
            "qualified": standing.qualified,
            "points_to_cut": standing.points_to_cut,
            "entries": len(entries),
        })

    rows.sort(key=lambda r: (-r["total_points"], r["name"]))

    for i, row in enumerate(rows):
        row["rank"] = i + 1
        if i == 0:
            row["gap_to_above"] = 0
        else:
            row["gap_to_above"] = rows[i - 1]["total_points"] - row["total_points"]

    return rows
