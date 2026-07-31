"""Seed the database with a realistic demo cohort so the board looks alive.

Run:  python -m app.seed
"""

from __future__ import annotations

from datetime import date

from . import create_app
from .models import db, Submission, Season
from .scoring import score_entry


DEMO = [
    # name, team, activity_type, title, impact_measured, highly_scalable, status
    ("Priya Nair", "Payments", "poc_demoed", "Auto-retry agent for flaky tests", True, False, "Approved"),
    ("Priya Nair", "Payments", "certification", "Prompt Engineering cert", False, False, "Approved"),
    ("Priya Nair", "Payments", "use_case_submitted", "Devin for migration scripts", False, True, "Approved"),
    ("Priya Nair", "Payments", "reusable_component", "Retry-agent library", False, False, "Approved"),

    ("Arjun Rao", "Platform", "poc_demoed", "Log-triage assistant", True, False, "Approved"),
    ("Arjun Rao", "Platform", "course", "Agentic AI foundations", False, False, "Approved"),
    ("Arjun Rao", "Platform", "use_case_submitted", "Devin for on-call runbooks", False, False, "Approved"),

    ("Meera Iyer", "Data", "poc_chartered", "PII redaction pipeline", False, False, "Approved"),
    ("Meera Iyer", "Data", "certification", "LangGraph specialist", False, False, "Approved"),
    ("Meera Iyer", "Data", "taught_session", "Intro to embeddings", False, False, "Approved"),
    ("Meera Iyer", "Data", "reusable_component", "Redaction middleware", False, False, "Approved"),

    ("Sam Fernandez", "Web", "poc_demoed", "Copilot code-review bot", False, False, "Approved"),
    ("Sam Fernandez", "Web", "course", "Responsible AI", False, False, "Approved"),

    ("Divya Menon", "Mobile", "certification", "GenAI practitioner", False, False, "Approved"),
    ("Divya Menon", "Mobile", "course", "Prompting patterns", False, False, "Approved"),
    ("Divya Menon", "Mobile", "poc_demoed", "Release-notes generator", True, False, "Pending"),

    ("Karan Shah", "Infra", "poc_demoed", "IaC drift detector", True, False, "Pending"),
]


def run() -> None:
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        db.session.add(Season(name="Season 1", seats_total=5, seats_filled=1,
                              closes_on=date(2026, 8, 14)))

        for name, team, activity, title, measured, scalable, status in DEMO:
            scored = score_entry(activity, impact_measured=measured,
                                 highly_scalable=scalable)
            db.session.add(Submission(
                name=name, team=team, track=scored.track.value,
                activity_type=activity, title=title,
                description=f"{title} \u2014 demo entry.",
                evidence_url="https://github.com/example/repo",
                impact_measured=measured, highly_scalable=scalable,
                points=scored.points, status=status,
            ))

        db.session.commit()
        print(f"Seeded {len(DEMO)} submissions across 6 engineers.")


if __name__ == "__main__":
    run()
