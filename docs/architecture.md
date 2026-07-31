# Architecture

## Overview

The Devin Draft is a small Flask application with four concerns kept
deliberately separate so each can be reasoned about and tested on its own:

1. **Rules** — how points work (`app/scoring.py`)
2. **Capture** — how an entry is collected (`app/agent.py`)
3. **State** — how entries are stored and approved (`app/models.py`)
4. **Presentation** — the board, dashboard, and chat (`app/routes.py`, templates)

The guiding rule: the scoring logic has no idea Flask or SQLite exist, and the
agent has no idea how points are stored. Dependencies point inward toward the
pure rules, never outward.

## Control flow of a submission

```
1. User opens /submit and talks to the Draft Desk (MockIntakeAgent).
2. The agent asks one question at a time, validating as it goes:
     - track and activity must be from the known set
     - a POC's business value must be quantified (number or before/after)
3. On completion the agent emits a structured Submission (a plain dict).
4. The frontend POSTs it to /api/submissions.
5. The route scores it via scoring.score_entry() and stores it as Pending.
6. A lead opens /review and approves or rejects it (the human sign-off gate).
7. /api/leaderboard aggregates only Approved entries, applies the fluency cap
   and qualification gate per person, and returns a ranked board with
   near-miss gaps.
```

The key property: **points are never trusted from the client.** The client
sends an activity type and two boolean flags; the server computes the points.
Even the track is derived from the activity, not accepted from the caller, so a
submission cannot claim points under the wrong track.

## The scoring engine

`scoring.py` is a set of pure functions over dataclasses. Two decisions are
worth calling out:

### The 25% fluency cap

Learning is the entry ticket, not the win condition, so AI Fluency points may
supply at most 25% of a person's total. The maths:

```
fluency_counted ≤ 0.25 × (fluency_counted + other)
⇒ fluency_counted ≤ (0.25 / 0.75) × other = other / 3
```

So someone with 90 points of POC/use-case work can bank at most 30 fluency
points, no matter how many certificates they hold. This is enforced in
`_apply_fluency_cap` and covered by `test_fluency_cap_*`.

### The qualification gate

Two conditions, both required:

- total (post-cap) ≥ 250
- at least one approved entry in **all three** tracks

This prevents a person from qualifying by grinding a single track. A contributor
with 300 points all in POCs is *not* qualified.

## The agent interface

```python
class IntakeAgent(ABC):
    def start(self) -> AgentReply: ...
    def step(self, state: dict, user_message: str) -> AgentReply: ...
```

`state` is a plain dict carried in the Flask session between turns, which keeps
the agent itself stateless and trivial to unit-test (no HTTP needed — see
`test_mock_agent_*`).

`MockIntakeAgent` walks a fixed question order as a small state machine. The
business-value validator (`looks_quantified`) is a regex looking for a digit or
comparison language; a vague answer is bounced with a concrete example of what
"good" looks like, rather than silently accepted.

A production version would implement the same interface with an LLM that reads
the conversation and fills the same `Submission` fields — the boundary is drawn
so that swapping the agent touches nothing downstream.

## Data model

Two tables:

- `submissions` — one row per entry. `points` is computed on write and stored so
  the board reads a stable number, but `scoring.py` remains the source of truth
  for how that number is produced. `status` gates visibility.
- `seasons` — a single active row holds the seat count and close date that drive
  the scarcity UI.

## Deliberate limitations

This is a reference implementation, not a production deployment. Known
simplifications, each an obvious next step:

- **Auth** — none. Anyone can approve. A real deployment gates `/review` and the
  status API behind a lead role.
- **Seat renewal / decay** — the 90-day lease and 10%/month decay are in the
  concept and the README but not yet implemented in the engine.
- **Concurrency** — SQLite is fine for a demo and a small cohort; a larger
  program would move to Postgres.
- **Adoption multiplier** — "adopted by another team, per team" is modelled as a
  flat 60 here rather than a per-team multiplier.

These are called out rather than hidden because knowing where the edges are is
part of the design.
