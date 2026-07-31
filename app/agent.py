"""The intake agent.

The agent interviews a submitter one question at a time, validates that a POC's
business value is actually quantified, and emits a structured submission ready
for scoring. It is deliberately built behind an interface: `MockIntakeAgent`
runs with zero setup (no API key, fully deterministic, easy to test), while a
real LLM-backed agent can be dropped in later without touching the routes or
the frontend.

This mirrors the production design principle the program itself teaches:
the AI proposes structure, a human owns the outcome.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field as dc_field, asdict

from .scoring import ACTIVITY_TRACK, score_entry


# Activities offered per track, with the questions each one needs.
TRACK_ACTIVITIES = {
    "AI Fluency": ["course", "certification", "taught_session",
                   "learning_plan", "prompt_published"],
    "AI POC": ["poc_chartered", "poc_demoed", "poc_adopted"],
    "Devin Use Case": ["use_case_submitted", "reusable_component"],
}

# A friendly label for each activity, shown to the user.
ACTIVITY_LABEL = {
    "course": "Completed a course or module",
    "certification": "Earned a certification",
    "taught_session": "Ran a hands-on session",
    "learning_plan": "Filed a team learning plan",
    "prompt_published": "Published a prompt or pattern",
    "poc_chartered": "Chartered a POC",
    "poc_demoed": "Demoed a working POC",
    "poc_adopted": "POC adopted by another team",
    "use_case_submitted": "Submitted a Devin use case",
    "reusable_component": "Published a reusable component",
}


@dataclass
class Submission:
    """The structured result of a completed interview."""
    name: str = ""
    team: str = ""
    track: str = ""
    activity_type: str = ""
    title: str = ""
    description: str = ""
    evidence_url: str = ""
    impact_measured: bool = False
    highly_scalable: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentReply:
    """One turn of the conversation."""
    message: str
    done: bool = False
    submission: dict | None = None
    field: str | None = None          # which field this question fills
    options: list[str] = dc_field(default_factory=list)  # for choice questions


class IntakeAgent(ABC):
    """Interface every intake agent implements."""

    @abstractmethod
    def start(self) -> AgentReply:
        ...

    @abstractmethod
    def step(self, state: dict, user_message: str) -> AgentReply:
        ...


# --- validation helpers -------------------------------------------------

_METRIC_RE = re.compile(
    r"\d|\b(before|after|from .* to |reduced|cut|increased|decreased|"
    r"faster|slower|saved|%|percent|hours?|days?|minutes?)\b",
    re.IGNORECASE,
)


def looks_quantified(text: str) -> bool:
    """True if a business-value statement contains a real number or a
    before/after comparison, rather than a vague claim."""
    return bool(_METRIC_RE.search(text or ""))


class MockIntakeAgent(IntakeAgent):
    """A deterministic, rule-based interviewer.

    It walks a small state machine of questions. State is a plain dict so it
    can be carried in the HTTP session between turns and is trivial to test.
    """

    ORDER = ["name", "team", "track", "activity_type", "title",
             "description", "business_value", "evidence_url"]

    def start(self) -> AgentReply:
        return AgentReply(
            message=("Welcome to the Draft Desk. Let's log your entry. "
                     "First up \u2014 what's your name?"),
            field="name",
        )

    def step(self, state: dict, user_message: str) -> AgentReply:
        answers = state.setdefault("answers", {})
        current = state.get("field")
        msg = (user_message or "").strip()

        if current:
            error = self._validate(current, msg, answers)
            if error:
                return AgentReply(message=error, field=current,
                                  options=self._options(current, answers))
            self._record(current, msg, answers)

        return self._next(answers)

    # -- internals --

    def _next(self, answers: dict) -> AgentReply:
        for f in self.ORDER:
            if f == "business_value":
                # only asked for POCs
                if answers.get("track") == "AI POC" and "business_value" not in answers:
                    return AgentReply(
                        message=("What's the business or engineering impact? "
                                 "Give a number or a before/after \u2014 "
                                 "\"improves productivity\" won't cut it."),
                        field="business_value",
                    )
                continue
            if f not in answers:
                return self._ask(f, answers)

        return self._finish(answers)

    def _ask(self, f: str, answers: dict) -> AgentReply:
        prompts = {
            "name": "What's your name?",
            "team": "Which team are you on?",
            "track": "Which track is this entry for?",
            "activity_type": "What did you do?",
            "title": "Give it a short title.",
            "description": "Describe it in a sentence or two.",
            "evidence_url": ("Last thing \u2014 paste an evidence link "
                             "(repo, demo recording, or certificate)."),
        }
        return AgentReply(message=prompts[f], field=f,
                          options=self._options(f, answers))

    def _options(self, f: str, answers: dict) -> list[str]:
        if f == "track":
            return list(TRACK_ACTIVITIES.keys())
        if f == "activity_type":
            track = answers.get("track", "")
            return [ACTIVITY_LABEL[a] for a in TRACK_ACTIVITIES.get(track, [])]
        return []

    def _validate(self, f: str, msg: str, answers: dict) -> str | None:
        if not msg:
            return "I didn't catch that \u2014 could you type an answer?"
        if f == "track" and msg not in TRACK_ACTIVITIES:
            return (f"Please pick one of: {', '.join(TRACK_ACTIVITIES)}.")
        if f == "activity_type":
            track = answers.get("track", "")
            valid = {ACTIVITY_LABEL[a]: a for a in TRACK_ACTIVITIES.get(track, [])}
            if msg not in valid:
                return f"Pick one of: {', '.join(valid)}."
        if f == "business_value" and not looks_quantified(msg):
            return ("That reads a bit vague. What's the actual number or "
                    "before/after? For example: \"cut build time from 40 to "
                    "12 minutes\".")
        if f == "evidence_url" and not (msg.startswith("http") or "/" in msg):
            return "That doesn't look like a link. Paste a URL to your evidence."
        return None

    def _record(self, f: str, msg: str, answers: dict) -> None:
        if f == "activity_type":
            track = answers.get("track", "")
            label_to_key = {ACTIVITY_LABEL[a]: a
                            for a in TRACK_ACTIVITIES.get(track, [])}
            answers[f] = label_to_key[msg]
        else:
            answers[f] = msg
        if f == "business_value":
            answers["impact_measured"] = True  # passed validation => quantified

    def _finish(self, answers: dict) -> AgentReply:
        sub = Submission(
            name=answers.get("name", ""),
            team=answers.get("team", ""),
            track=answers.get("track", ""),
            activity_type=answers.get("activity_type", ""),
            title=answers.get("title", ""),
            description=answers.get("description", ""),
            evidence_url=answers.get("evidence_url", ""),
            impact_measured=answers.get("impact_measured", False),
            highly_scalable=False,
        )
        scored = score_entry(
            sub.activity_type,
            impact_measured=sub.impact_measured,
            highly_scalable=sub.highly_scalable,
        )
        return AgentReply(
            message=(f"Got it. \"{sub.title}\" is worth about "
                     f"{scored.points} points, filed under {sub.track}. "
                     "It'll sit as Pending until your lead approves it. "
                     "Nice work."),
            done=True,
            submission=sub.to_dict(),
        )
