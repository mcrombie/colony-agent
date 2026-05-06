# Colony Agent

Colony Agent is a small stateful Python simulation. Each run advances the fictional colony of Blergen by one day, asks one AI role what happens to the colony, asks another AI role how the colony responds, applies deterministic effects, writes a short history entry, and saves the updated state.

The selectors use the OpenAI API. Missing OpenAI configuration is treated as an error so runs do not silently fall back to random events. If the deity call fails, the colony receives a special `chaos_gods` event. If the president call fails, the colony falls back to `preserve_resources`.

## Why this is an agentic loop

The project has a simple observe-decide-respond-act-record loop:

1. Observe the current colony state from `src/state.json`.
2. Ask the deity selector which world event befalls Blergen.
3. Ask the president selector how colony leadership responds to that event.
4. Act by applying deterministic mechanical effects to the state.
5. Consume daily food, with starvation reducing population if food runs out.
6. Record the result in `event_log` and `src/history.md`.
7. Persist the new state for the next run.

Because the next run depends on the saved result of the previous run, the loop is stateful.

## Individual colonists

Older state files can store `population` as only a number. When a day runs now,
the simulation upgrades that state with a `people` list containing one living
colonist per population member. Each colonist has a stable ID, distinct name,
role, personality, status, relationship placeholders, and personal story notes.

The current aggregate mechanics still drive the simulation. When those mechanics
reduce population, the loss is assigned to named colonists, those colonists are
marked dead, and the day's event record includes their death records. The daily
history entry also names colonists who died.

Daily world events and leadership actions also touch individual colonists. For
example, illness can name who fell sick, disputes can create rivalries, discovery
credits a scout or forager, and work orders name the colonists who took part.
These personal consequences are saved in each colonist's story notes and in the
day's `people_events` record.

`population`, `health`, and `morale` are derived from the living colonists.
Population is the count of living people, while health and morale are integer
averages of living colonists' personal status values. Food, wood, security, and
known threats remain colony-level fields.

The OpenAI selectors receive a bounded `character_context` section with role
counts, status summaries, and a small set of relevant named colonists. The deity
prompt sees current vulnerabilities and recent stories. The president prompt
gets colonists relevant to the chosen world event, such as sick colonists during
illness, rivals during disputes, or scouts during discoveries. OpenAI still only
chooses from the allowed event and action labels.

The readable archive is split in two:

- `src/history.md` records the colony-level chronicle.
- `src/people_history.md` records individual colonist moments as bullet points
  with personal status changes. The durable machine-readable version of each
  colonist's story remains in `src/state.json`.

## Run one day

From the project root:

```powershell
python -m pip install -r requirements.txt
python -m src.run_day
```

This updates `src/state.json` and appends one paragraph to `src/history.md`.

## OpenAI selectors

Create `.env.local` in the project root:

```text
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-5.4-mini
```

When `OPENAI_API_KEY` is missing, `python -m src.run_day` fails before advancing the colony.

The OpenAI selectors only choose from allowed labels. The mechanical effects still come from deterministic local code.

The deity selector is prompted as a deity deciding what event, if any, should befall Blergen. It can choose:

```text
good_harvest, poor_harvest, illness, dispute, discovery, quiet_day
```

The prompt asks the deity to choose `quiet_day` often so many days leave room for the colonists to take initiative.

The president selector is prompted as the president of Blergen deciding how to respond to the event. It can choose:

```text
preserve_resources, ration_food, gather_wood, expand_fields,
strengthen_defenses, tend_the_sick, mediate_dispute, send_scouts,
hold_festival
```

If the deity API call fails after configuration is present, the simulation records `chaos_gods`: health -1, security -1, and morale -1.

If the president API call fails after configuration is present, the simulation uses `preserve_resources`.

If the president chooses `strengthen_defenses` when the colony has fewer than 10 wood, the simulation records `failed_strengthen_defenses` instead and leaves wood, security, and morale unchanged.

Food is consumed every day regardless of events or leadership actions. If food reaches zero, population falls until food recovers.

## Run tests

Install dependencies if needed:

```powershell
python -m pip install -r requirements.txt
```

Then run:

```powershell
python -m pytest
```

## GitHub Actions

The workflow in `.github/workflows/advance-colony.yml` runs once per day and can also be started manually from the Actions tab.

Before enabling it on GitHub, add this repository secret:

```text
OPENAI_API_KEY
```

Optionally add this repository variable to override the default model:

```text
OPENAI_MODEL
```

Each run installs dependencies, runs tests, advances the colony once, and commits changes to `src/state.json` and `src/history.md`.

The daily schedule is:

```yaml
- cron: "17 11 * * *"
```

GitHub cron uses UTC, so this is about 7:17 AM Eastern during daylight time and 6:17 AM Eastern during standard time. GitHub can delay scheduled runs during busy periods, so the exact start time may drift a little. Manual runs still advance immediately.

## Roadmap

1. Add an OpenAI API event selector. Done.
2. Add a GitHub Actions daily run. Done.
3. Publish `history.md` to Cromblog.
4. Add charts and long-term summaries.
