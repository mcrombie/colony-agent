# Colony Agent

Colony Agent is a small stateful Python simulation. Each run advances the fictional colony of Blergen by one day, asks one AI role what happens to the colony, asks another AI role how the colony responds, applies deterministic effects, writes a short history entry, and saves the updated state.

The selectors use the OpenAI API. Missing OpenAI configuration is treated as an error so runs do not silently fall back to random events. If the deity call fails, the colony receives a special `chaos_gods` event. If the president call fails, the colony falls back to `preserve_resources`.

## Why this is an agentic loop

The project has a simple observe-decide-respond-act-record loop:

1. Observe the current colony state from `src/state.json`.
2. Ask the deity selector which world event befalls Blergen.
3. Ask the president selector how colony leadership responds to that event.
4. Derive the day's calendar date, season, and weather.
5. Act by applying deterministic weather, event, leadership, and survival effects.
6. Consume daily food, with each living colonist needing 1 food per day.
7. Record the result in `event_log` and `src/history.md`.
8. Persist the new state for the next run.

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

The colony president is also a specific living colonist. The saved state tracks
their `id`, `name`, and first day in office. If no living president exists, the
simulation deterministically selects one from the living colonists before asking
for a leadership action. If the colony has no living people, the office is
removed until new settlers arrive.

`population`, `health`, and `morale` are derived from the living colonists.
Population is the count of living people, while health and morale are integer
averages of living colonists' personal status values. Food, wood, security, and
known threats remain colony-level fields.

## Seasons, weather, and threats

Day 1 is January 1 of year 1 in the colony calendar. The saved state tracks the
current year, and dates are derived from the saved day number, so day 50 is
February 19 of year 1 and day 366 is January 1 of year 2. The simulation uses
four seasons:

- Winter: December, January, February
- Spring: March, April, May
- Summer: June, July, August
- Autumn: September, October, November

Every day has deterministic weather based on the day and season. Weather is
recorded in the event log and can have small mechanical effects, such as snow
costing wood, hard freezes hurting health, or severe winter weather lowering
morale.

`known_threats` now affects what events are available to the selector. `wolves`
can become a `wolf_attack`, and `winter` raises the importance of winter weather
and storm danger. Winter itself is not an event; it is a season that shapes the
weather table and the prompt context.

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

This updates `src/state.json`, appends one paragraph to `src/history.md`, and appends any personal story beats to `src/people_history.md`.

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
good_harvest, poor_harvest, illness, dispute, discovery,
storm, wolf_attack, quiet_day
```

The prompt asks the deity to favor impactful events and choose `quiet_day` only
about 15 to 25 percent of the time. `storm` and `wolf_attack` include a
severity from 1 to 5. Stronger wolf attacks can kill colonists, especially when
security is low. Stronger storms can damage stores, wood, health, morale, and in
extreme sickly conditions, population.

The president selector is prompted as the president of Blergen deciding how to respond to the event. It can choose:

```text
preserve_resources, ration_food, gather_wood, expand_fields,
strengthen_defenses, tend_the_sick, mediate_dispute, send_scouts,
hold_festival
```

If the deity API call fails after configuration is present, the simulation records `chaos_gods`: health -1, security -1, and morale -1.

If the president API call fails after configuration is present, the simulation uses `preserve_resources`.

If the president chooses `strengthen_defenses` when the colony has fewer than 10 wood, the simulation records `failed_strengthen_defenses` instead and leaves wood, security, and morale unchanged.

If the president chooses `strengthen_defenses` during a wolf attack and the
colony has enough wood, the attack's effective severity is reduced by one level.

Food is consumed every day regardless of events or leadership actions. Each
living colonist needs 1 food per day. If there is not enough food, named
colonists miss rations and their hunger rises. Severe hunger causes named
starvation deaths, reducing population.

Food-producing events and actions scale with the current living population.
`good_harvest` produces about five days of food, while `expand_fields` produces
about three days of food, with small-colony minimums so a diminished settlement
can still recover. Food-costing actions such as `hold_festival` and
`tend_the_sick` also scale with population.

If population reaches 0, the colony becomes inert. Daily runs no longer ask the
deity or president selectors for choices; the event log records an
`empty_colony` day with `no_action` until future mechanics add new colonists.

## Blergen Company interventions

Blergen Company can intervene before the normal daily event and leadership
choices by passing flags to the same command that advances the colony. The
intervention is recorded in the day's event log.

Send 100 new settlers:

```powershell
python -m src.run_day --send-settlers
```

Send a custom number of settlers:

```powershell
python -m src.run_day --send-settlers 25
```

Send food:

```powershell
python -m src.run_day --send-food 200
```

Send supplies. With no values, this defaults to 50 wood and 2 security:

```powershell
python -m src.run_day --send-supplies
```

Send custom supplies:

```powershell
python -m src.run_day --send-supplies 80 3
```

Multiple interventions can be combined and are applied in order:

```powershell
python -m src.run_day --send-settlers --send-food 300 --send-supplies
```

The lower-level top-level `company_interventions` queue in `src/state.json` is
still supported for scripts, but CLI flags are the intended manual interface.

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

Each run installs dependencies, runs tests, advances the colony once, and commits changes to `src/state.json`, `src/history.md`, and `src/people_history.md`.

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
