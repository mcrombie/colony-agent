# Colony Agent

Colony Agent is a small stateful Python simulation. Each run advances the fictional colony of Blergen by one day, chooses one event from the current state, applies deterministic effects, writes a short history entry, and saves the updated state.

The event selector can use the OpenAI API, with a rule-based selector still available for local testing and fallback development.

## Why this is an agentic loop

The project has a simple observe-decide-act-record loop:

1. Observe the current colony state from `src/state.json`.
2. Decide which event should happen with the configured event selector.
3. Act by applying mechanical effects to the state.
4. Record the result in `event_log` and `src/history.md`.
5. Persist the new state for the next run.

Because the next run depends on the saved result of the previous run, the loop is stateful.

## Run one day

From the project root:

```powershell
python -m pip install -r requirements.txt
python -m src.run_day
```

This updates `src/state.json` and appends one paragraph to `src/history.md`.

## OpenAI selector

Create `.env.local` in the project root:

```text
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-5.4-mini
```

When `OPENAI_API_KEY` is present, `python -m src.run_day` uses the OpenAI selector by default. To force local rules instead:

```powershell
$env:COLONY_EVENT_SELECTOR = "rules"
python -m src.run_day
```

The OpenAI selector only chooses one allowed event type. The mechanical effects still come from deterministic local code.

## Run tests

Install dependencies if needed:

```powershell
python -m pip install -r requirements.txt
```

Then run:

```powershell
python -m pytest
```

## Roadmap

1. Add an OpenAI API event selector. Done.
2. Add a GitHub Actions daily run.
3. Publish `history.md` to Cromblog.
4. Add charts and long-term summaries.
