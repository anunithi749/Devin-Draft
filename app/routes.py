"""HTTP routes: server-rendered pages plus a small JSON API."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from flask import Blueprint, render_template, request, jsonify, session

from .models import db, Submission, Season
from .scoring import ScoredEntry, Track, build_leaderboard, QUALIFYING_SCORE
from .agent import MockIntakeAgent

bp = Blueprint("main", __name__)
agent = MockIntakeAgent()


# -- helpers -------------------------------------------------------------

def _active_season() -> Season:
    season = Season.query.first()
    if season is None:
        season = Season(name="Season 1", seats_total=5, seats_filled=0,
                        closes_on=date(2026, 8, 14))
        db.session.add(season)
        db.session.commit()
    return season


def _leaderboard_rows() -> list[dict]:
    """Build the leaderboard from approved submissions only."""
    approved = Submission.query.filter_by(status="Approved").all()
    by_person: dict[str, list[ScoredEntry]] = defaultdict(list)
    for s in approved:
        by_person[s.name].append(
            ScoredEntry(activity_type=s.activity_type,
                        track=Track(s.track),
                        points=s.points)
        )
    return build_leaderboard(by_person)


# -- pages ---------------------------------------------------------------

@bp.route("/")
def index():
    season = _active_season()
    rows = _leaderboard_rows()
    days_left = None
    if season.closes_on:
        days_left = max(0, (season.closes_on - date.today()).days)
    stats = {
        "total": Submission.query.count(),
        "approved": Submission.query.filter_by(status="Approved").count(),
        "pending": Submission.query.filter_by(status="Pending").count(),
        "qualified": sum(1 for r in rows if r["qualified"]),
    }
    return render_template("index.html", season=season.to_dict(),
                           rows=rows, stats=stats, days_left=days_left,
                           qualifying=QUALIFYING_SCORE)


@bp.route("/submit")
def submit():
    return render_template("submit.html")


@bp.route("/board")
def board():
    season = _active_season()
    rows = _leaderboard_rows()
    return render_template("board.html", rows=rows, season=season.to_dict(),
                           qualifying=QUALIFYING_SCORE)


@bp.route("/review")
def review():
    pending = (Submission.query.filter_by(status="Pending")
               .order_by(Submission.created_at).all())
    return render_template("review.html",
                           submissions=[s.to_dict() for s in pending])


# -- agent API -----------------------------------------------------------

@bp.route("/api/agent/start", methods=["POST"])
def agent_start():
    reply = agent.start()
    session["intake"] = {"field": reply.field, "answers": {}}
    return jsonify({"message": reply.message, "done": reply.done,
                    "options": reply.options})


@bp.route("/api/agent/message", methods=["POST"])
def agent_message():
    state = session.get("intake") or {"field": None, "answers": {}}
    user_message = (request.json or {}).get("message", "")

    reply = agent.step(state, user_message)

    # persist advancing state
    if not reply.done:
        state["field"] = reply.field
        session["intake"] = state
    else:
        session.pop("intake", None)

    return jsonify({
        "message": reply.message,
        "done": reply.done,
        "options": reply.options,
        "submission": reply.submission,
    })


@bp.route("/api/submissions", methods=["POST"])
def create_submission():
    """Persist a completed interview as a Pending submission."""
    data = request.json or {}
    from .scoring import score_entry
    try:
        scored = score_entry(
            data.get("activity_type", ""),
            impact_measured=bool(data.get("impact_measured")),
            highly_scalable=bool(data.get("highly_scalable")),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    sub = Submission(
        name=data.get("name", "").strip() or "Anonymous",
        team=data.get("team", ""),
        track=scored.track.value,
        activity_type=scored.activity_type,
        title=data.get("title", "").strip() or "Untitled",
        description=data.get("description", ""),
        evidence_url=data.get("evidence_url", ""),
        impact_measured=bool(data.get("impact_measured")),
        highly_scalable=bool(data.get("highly_scalable")),
        points=scored.points,
        status="Pending",
    )
    db.session.add(sub)
    db.session.commit()
    return jsonify(sub.to_dict()), 201


@bp.route("/api/submissions/<int:sub_id>/status", methods=["POST"])
def set_status(sub_id: int):
    """Approve or reject. This is the human sign-off gate."""
    sub = db.session.get(Submission, sub_id)
    if sub is None:
        return jsonify({"error": "Not found"}), 404
    new_status = (request.json or {}).get("status", "")
    if new_status not in ("Approved", "Rejected", "Pending"):
        return jsonify({"error": "Invalid status"}), 400
    sub.status = new_status
    db.session.commit()
    return jsonify(sub.to_dict())


@bp.route("/api/leaderboard")
def api_leaderboard():
    return jsonify(_leaderboard_rows())
