# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

A Home Assistant custom integration plus its Lovelace card. It drives a
physical switch (typically a boiler) on timers and tracks daily runtime. The
failure modes that matter most are **the device acting on its own** and **a
timer silently vanishing** — weight testing accordingly.

## Commands

```bash
# Tests — HA is stubbed, no HA install needed. pytest is NOT installed.
cd tests && python -m unittest discover -s . -p "test_*.py"

# A single test file / case / method
cd tests && python -m unittest test_schedule
cd tests && python -m unittest test_schedule.FiringFailureTestCase
cd tests && python -m unittest test_schedule.FiringFailureTestCase.test_one_shot_clears_when_the_timer_fails_to_start

# Card bundle -> custom_components/simple_timer/dist/timer-card.js
npm install && npm run build

# Verify a build the way CI does (see "Releasing")
rm -rf node_modules && npm install && npm run build
```

Two local commands live in `.claude/` (gitignored here): `/release <version>`
walks the full release sequence, and `/verify-dev` checks a deployed change
against the dev Home Assistant over its REST API — timer instances and their
published attributes, service calls, the integration's log, and whether the
served bundle matches the local build. The card has no test harness, so that
command is the only thing standing between a card change and a user finding the
bug. Its credentials come from `deploy_config.bat`, which also holds the **prod**
url and token; only ever reach the dev instance through
`.claude/scripts/ha-dev.ps1`, which refuses a non-local host.

## Architecture

**Two entities per config entry, deliberately.** `TimerRuntimeSensor`
(`sensor.py`) holds daily runtime as a number, which means it carries a
`unit_of_measurement` — and HA's logbook filters numeric sensors out entirely.
So a second, non-numeric `TimerStatusSensor` (`status_sensor.py`) exists purely
to be loggable: its states are `idle` / `active` / `delayed_start` /
`scheduled`. That is what makes timers appear in a device's Activity feed.

The status sensor stays in sync via a dispatcher signal
(`SIGNAL_STATE_UPDATED`, formatted per `entry_id`) fired from the runtime
sensor's `async_write_ha_state` override — rather than patching ~30 individual
write sites.

**`sensor.py` is the entity; everything else is a collaborator it delegates
to.** `timer_store` (the `.storage` payload and its validation), `notify`
(dispatch + target validation), `switch_control` (commanding the switch and
making it stick), `schedule` (future clock-time starts), `startup` (waiting for
HA readiness), `helpers` (pure functions, the instance logger), `logbook`,
`const`. Collaborators reach back into the sensor only through injected
callables, so the import graph stays a DAG. Keep it that way.

**Services live in `__init__.py`**, not on the entity — 11 of them
(`start_timer`, `add_timer`, `schedule_timer`, `cancel_schedule`,
`cancel_timer`, …). Each accepts `entry_id` **or** `entity_id` but not both
(`vol.Exclusive`), then resolves to the sensor instance through
`hass.data[DOMAIN][entry_id]["sensor"]`. Adding a service means touching
`__init__.py`, `services.yaml`, and usually the card.

**Timer modes.** A *normal* timer runs the device for a duration then switches
it off. A *reverse* timer ("delayed start") counts down and switches the device
**on** at the end. A *schedule* arms a wall-clock time and then runs a normal
timer. Reverse mode is **decoupled**: arming one says only "turn it on at
time T" and makes no claim about the device before then — the device may
already be on, and its runtime still counts toward daily usage.

**The card is built and committed.** `src/timer-card.ts` → rollup →
`custom_components/simple_timer/dist/timer-card.js`, which is checked in
because that bundle is what ships to users. Editing the `.ts` without
rebuilding changes nothing for them.

## Tests

`tests/ha_harness.py` installs a mock `homeassistant` package tree at import
time plus a *real* `simple_timer` package entry, so `load("sensor")` and
friends import normally. Do not revert the package to a `MagicMock` — CPython
reads `parent_module.__spec__` during submodule import, which a MagicMock
raises `AttributeError` for, breaking every sibling import.

Two conventions the suite depends on:

- Many fixtures build a sensor via `object.__new__` rather than `__init__`, so
  they set only the attributes the code under test touches. Adding a new
  attribute read to a hot path (`async_start_timer`, `_async_timer_finished`)
  breaks them with `AttributeError`. **Fix the fixture, not the code** — do not
  add `getattr(self, "_x", default)`; those guards were deliberately removed.
- `asyncio.sleep` and `dt_util.utcnow` get patched on the *module object*,
  which is shared across test files. Always restore them in `tearDown`, or
  later suites silently skip their real waits.

When changing behaviour, verify a test actually pins it by reverting the fix
alone and confirming that test goes red. Tests here have repeatedly passed for
the wrong reason — e.g. two guards covering the same path, so deleting either
left the suite green.

## Releasing

Four places carry the version and must agree:

1. `custom_components/simple_timer/manifest.json`
2. `package.json`
3. `src/timer-card.ts` — `CARD_VERSION`
4. the built bundle — run `npm run build` after the first three

Publishing a GitHub release triggers `.github/workflows/release.yaml`, which
builds the card, zips `custom_components/simple_timer/` and attaches
`simple_timer.zip`. **HACS installs from that asset, not from the repo.** If
the workflow fails the release page looks perfectly normal while every user
gets a 404 — always confirm the run went green and the asset is attached.

`package-lock.json` is gitignored, so CI resolves dependencies fresh every
build and a passing local build proves nothing. Verify from an empty
`node_modules` before tagging. `typescript` and `tslib` must stay in
`devDependencies`: they are peer dependencies of `@rollup/plugin-typescript`
that older npm installed automatically and newer npm does not, and their
absence fails the build with
`Cannot read properties of undefined (reading 'ES2015')`.

## Things that bite

- `extra_state_attributes` on the runtime sensor is the card's public API. The
  `ATTR_*` names in `const.py` are read by shipped bundles that will never be
  rebuilt. Do not rename them.
- The card finds its instance by scanning every `sensor.*` for one carrying
  both `entry_id` and `switch_entity_id`, first match wins. Never add those
  attributes to another entity.
- `CARD_URL` must stay under an integration-owned path, never `/local/` —
  that is HA's static mount for `<config>/www/` and racing it 404s the card.
  `LEGACY_CARD_URL` exists only to clean up resources left by ≤ 1.5.0.
- `config_flow.py` calls several private sensor methods directly, so renaming
  them breaks the options flow without any test failing.
- `_timer_reverse_mode` is sticky by design. `async_cancel_timer` reads it
  *after* cleanup, so cleanup must never reset it.
- `SwitchController` takes a **getter** for the entity id, never a cached copy
   — the sensor assigns `_switch_entity_id` in three places.
- Python changes need a full Home Assistant restart; reloading the integration
  is not enough.

## Backlog

`docs/` is untracked on purpose — `.gitignore` excludes it wholesale, and it
carries local testing notes that must never reach the repo. Read it before
structural or correctness work:

- `TODO.md` — the correctness backlog and a "recurring mistakes" section.
- `DECISIONS.md` — why the code is shaped the way it is, and for each choice,
  what would change it. Read before reversing a design decision.
- `PLAN-*.md` — per-feature implementation plans. Expected to go stale once
  their feature lands; the durable reasoning migrates to `DECISIONS.md`.
