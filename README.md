# Colony Agent

Colony Agent is a small stateful Python simulation. Each run advances the fictional colony of Blergen by one day, chooses one event from the current state, applies deterministic effects, writes a short history entry, and saves the updated state.

This first version does not call the OpenAI API. The event selector is intentionally rule-based and easy to replace later.

## Why this is an agentic loop

The project has a simple observe-decide-act-record loop:

1. Observe the current colony state from `src/colony_sim/state.json`.
2. Decide which event should happen with `choose_event`.
3. Act by applying mechanical effects to the state.
4. Record the result in `event_log` and `src/colony_sim/history.md`.
5. Persist the new state for the next run.

Because the next run depends on the saved result of the previous run, the loop is stateful.

## Run one day

From the project root:

```powershell
python -m pip install -e .
python -m colony_sim.run_day
```

This updates `src/colony_sim/state.json` and appends one paragraph to `src/colony_sim/history.md`.

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

1. Add an OpenAI API event selector.
2. Add a GitHub Actions daily run.
3. Publish `history.md` to Cromblog.
4. Add charts and long-term summaries.
