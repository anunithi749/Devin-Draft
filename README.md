# The Devin Draft

An AI-assisted, gamified upskilling tracker. Engineers earn a scarce resource —
seats to an AI coding tool — by learning AI, shipping proofs of concept, and
proposing where the tool helps their team. A conversational agent captures each
entry, a scoring engine ranks contributors, and a live draft board turns an
internal training mandate into a contest.

> Built as a working reference implementation of a concept originally prototyped
> on the Microsoft 365 stack (SharePoint + Power Automate + Copilot). This repo
> reimplements the idea as a self-contained Flask app so it runs anywhere with
> zero external services.

## Why it exists

Adoption mandates ("everyone learn AI") tend to be ignored. This turns the
mandate into a game with three ingredients from behavioural design:

- **Scarcity** — a fixed, visible number of seats.
- **Loss aversion** — seats are 90-day leases, not gifts; unrenewed seats return
  to the pool.
- **Near-miss feedback** — the board shows each person exactly how far they are
  from the cut, and who just passed them.

## What's interesting technically

- **A pure scoring engine** (`app/scoring.py`) with no framework or DB
  dependencies — the rules are fully unit-tested in isolation. It enforces a
  25% cap on how much "learning" points can contribute (so nobody qualifies on
  certificates alone) and a qualification gate requiring coverage of all three
  tracks.
- **An agent behind an interface** (`app/agent.py`). The included
  `MockIntakeAgent` is deterministic and needs no API key, so the app always
  runs. It interviews the user one question at a time and *pushes back on vague
  business value* — "improves productivity" is rejected; "cut build time from 40
  to 12 minutes" is accepted. A real LLM-backed agent implements the same
  `IntakeAgent` interface and drops in without touching routes or UI.
- **Human sign-off gate.** The agent proposes; a lead approves. Only approved
  entries reach the board — the same "AI assists, human owns the outcome"
  principle the program teaches.

## Architecture

```
Browser (chat + board)
      │
      ▼
Flask routes  ──►  IntakeAgent (MockIntakeAgent | LLM adapter)
      │                    │ structured submission
      │                    ▼
      │            scoring.py  (pure rules: points, caps, gate)
      ▼                    │
SQLAlchemy / SQLite ◄──────┘   status: Pending → Approved
      │
      ▼
Leaderboard  (approved entries → ranked board with near-miss gaps)
```

See [`docs/architecture.md`](docs/architecture.md) for the full walkthrough,
the scoring model, and the design decisions.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate   # optional
pip install -r requirements.txt

python -m app.seed        # load a demo cohort so the board isn't empty
python run.py             # http://localhost:5000
```

Pages:

- `/` — dashboard: seats remaining, countdown, top of the board
- `/board` — the full draft board
- `/submit` — chat with the Draft Desk to log an entry
- `/review` — approve or reject pending entries

## Test

```bash
pytest
```

21 tests cover the scoring rules (base points, bonuses, the fluency cap, the
qualification gate, leaderboard ranking and tie-breaks) and the API/agent flow
(vague-value pushback, pending-stays-off-board, approval-promotes-to-board).

## Scoring model

| Track | Activity | Points |
|---|---|---|
| AI Fluency *(max 25% of total)* | Course | 10 |
| | Certification | 25 |
| | Taught a session | 20 |
| | Learning plan filed | 15 |
| | Prompt/pattern published | 15 |
| AI POC | POC chartered | 30 |
| | POC demoed | 60 |
| | POC demoed **with measured impact** | 110 |
| | POC adopted by another team | 60 |
| Devin Use Case | Use case submitted | 40 |
| | …**rated highly scalable** | +40 |
| | Reusable component published | 50 |

**Qualify:** 250 points **and** at least one approved entry in all three tracks.

## Swapping in a real LLM

`MockIntakeAgent` implements `IntakeAgent`. To use a real model, implement the
same two methods (`start`, `step`) with an LLM call that fills the same
`Submission` fields, and construct that class in `app/routes.py` instead. Nothing
else changes — the scoring, storage, board, and tests are agent-agnostic.

## Project layout

```
app/
  scoring.py      pure scoring engine (no deps)
  agent.py        IntakeAgent interface + MockIntakeAgent
  models.py       SQLAlchemy models
  routes.py       pages + JSON API
  seed.py         demo cohort
  templates/      server-rendered pages
  static/         styling + chat JS
tests/            pytest suite
docs/             architecture notes
```

## License

MIT — see [LICENSE](LICENSE).
