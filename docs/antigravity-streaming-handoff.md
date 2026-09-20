# Antigravity Streaming Completion Handoff

Investigation date: 2026-09-20 (updated same day with a second investigation
into the `Stop` hook's `fullyIdle` signal, then a production fix once the user
authorized a global hook install in this dev container).

## Status and Scope

The user reported that `agypywpr` exited successfully before a background
subagent finished. Three live diagnostic/validation runs are complete, and
`runner.py` has been changed to fix the original issue: `run_agy` now uses the
streaming protocol and waits for the `Stop` hook's `fullyIdle` signal (when
available) before closing stdin.

## Stop Hook `fullyIdle` Investigation and Production Fix

The streaming `result` event marks the end of a turn, not necessarily the end
of all background subagent work. The CLI's `Stop` hook payload documents a
`fullyIdle` boolean ("true if the agent is completely finished and all
background commands or asynchronous tasks have completed") that is exactly the
missing signal.

Built and validated (offline tests plus three live runs):

- [scripts/agy_stop_signal_hook.py](../scripts/agy_stop_signal_hook.py): an
  observe-only `Stop` hook. It appends `conversationId`, `executionNum`,
  `terminationReason`, `error`, and `fullyIdle` to a file named by the
  `AGYPYWPR_STOP_SIGNAL_FILE` environment variable, and always returns `{}`
  (never `"decision": "continue"`), so it cannot itself trigger extra paid
  model turns or otherwise change AGY's own stop behavior.
- [.agents/hooks.json](../.agents/hooks.json): documents the intended
  workspace-scoped wiring, kept for when workspace-hook discovery is fixed
  upstream (see below — it is currently not the active copy).
- `~/.gemini/config/hooks.json` (outside the repo, **global**, not tracked in
  git): the copy actually discovered and used by the installed CLI. Installed
  with explicit user authorization ("Using a global hook is fine. This is in a
  dev container."). Points at absolute paths
  (`/workspaces/agypywpr/.venv/bin/python
  /workspaces/agypywpr/scripts/agy_stop_signal_hook.py`) since global hooks can
  run from any cwd. If this container/workspace path ever changes, this file
  needs to be regenerated or repointed.
- [tests/test_agy_stop_signal_hook.py](../tests/test_agy_stop_signal_hook.py):
  offline subprocess tests for the hook script itself.
- [scripts/diag_agy_probe.py](../scripts/diag_agy_probe.py) gained
  `--observe-stop-signal`, which points the child at a per-run stop-signal
  file, tails it during `observe()`, and records `stop_signal` entries in the
  JSONL log. Covered by
  [tests/test_diag_agy_probe.py](../tests/test_diag_agy_probe.py)'s
  `test_observes_stop_signal_transitions`.
- [src/tools/runner.py](../src/tools/runner.py): `run_agy` now speaks
  `--input-format stream-json --output-format stream-json` instead of `-p`,
  sends the prompt as one `user` event, prints the turn's `response` text as
  it did before, and — after the `result` event — waits up to
  `FULLY_IDLE_GRACE_SECONDS` (5s) for any Stop-hook observation for that
  conversation. If the hook is active but reports `fullyIdle: false`, it keeps
  waiting (bounded only by the overall `timeout`) until `true` is observed. If
  no observation ever appears (hook not installed on some other machine), it
  falls back to closing stdin after the grace period — never blocking forever
  on an absent hook.
- [tests/test_runner.py](../tests/test_runner.py) was rewritten for the
  streaming protocol: a grace-period fallback test, a
  wait-for-fullyIdle-before-closing test (using a fake `agy` that writes
  `fullyIdle: false` then `true` to the signal file, asserting `run_agy` really
  waited), and the existing timeout test.

### Live validation history

1. First live run (original investigation): confirmed streaming input/output
   works — a 60s subagent completed and the parent's `result` reported it —
   but did not explain when it is safe to close stdin in general.
2. Second live run (workspace hook): stop-signal file stayed empty.
   `agy -p "/hooks" --output-format json` showed `.agents/hooks.json` at the
   workspace root was **not discovered** by the installed CLI (`agy` 1.2.7),
   nor was a `.gemini/hooks.json` variant. The same content copied to the
   global `~/.gemini/config/hooks.json` was discovered
   (confirmed via `agy -p "/hooks"`, then removed since it was not yet
   authorized).
3. Third live run (global hook, authorized): reinstalled the same hook
   globally, confirmed discovery, then re-ran the one-minute-subagent probe.
   The **parent's own Stop event fired at 12.0s with `fullyIdle: false`**
   (right after invoking the subagent, while it was still running), and only
   flipped to `fullyIdle: true` at 74.7s, within the same second as the
   subagent's own `fullyIdle: true` (74.71s) and the stream's `result` event
   (75.32s). This is exactly the discriminating evidence needed: the hook
   correctly reports "not done" while background work is outstanding, and only
   reports "done" once it actually is.
4. End-to-end production validation: ran
   `python -m tools.cli run --prompt-file tests/test_prompt.txt --timeout 170`
   with the updated `runner.py` and the global hook installed. It printed the
   subagent-completion response and exited `0` after ~77 seconds (matching the
   subagent's real completion time), not the ~28s of the original bug report.

### Known caveats

- Workspace-level hook discovery (`.agents/hooks.json`) did not work on the
  installed CLI version in this container. The global hook is a workaround
  authorized specifically because this is a single-purpose dev container; it
  would need reconsideration on a shared or multi-project machine.
- The grace-period fallback (5s) means a machine where the global hook is
  later removed or misconfigured will silently revert to the old
  close-after-result behavior rather than failing loudly. This is intentional
  (never block forever on an absent hook) but means the fix is only as good as
  the hook staying installed and discoverable.
- Only one live subagent scenario has been exercised (a single lightweight
  `invoke_subagent` timer). Deeply nested subagents, multiple concurrent
  subagents, and detached "fire and forget" background work with no explicit
  parent wait have not been separately validated.

The live tests support switching to streaming input and using `fullyIdle`, but
do not establish a universal completion rule for arbitrary nested subagent
topologies.

## Original Failure

Command reported by the user:

```bash
time agypywpr run --prompt-file tests/test_prompt.txt
```

The parent said it had invoked a subagent to wait for one minute and would notify
the user when it finished. The process then exited `0` after 28.684 seconds,
without reporting completion.

[The runner](../src/tools/runner.py) currently launches
`[executable, "-p", prompt, *arguments]`. It creates a stdin pipe and leaves it
open, but never sends the prompt through that pipe. It waits only for process
exit and returns the child's status.

**Local hypothesis:** keeping stdin open does not control the lifetime of AGY's
single-prompt `-p` mode. The documented persistent session requires streaming
input, not merely an open pipe. A bounded streaming-input run was the
discriminating check.

## Documentation Findings

Sources consulted:

- [Headless mode](https://antigravity.google/docs/cli/headless/)
- [Subagent lifecycle](https://antigravity.google/docs/subagents/)
- [Lifecycle hooks](https://antigravity.google/docs/hooks/)
- Installed CLI help: `agy --help`

The headless documentation distinguishes two modes:

- `agy -p <prompt>` runs one prompt and exits.
- `agy --input-format stream-json --output-format stream-json` maintains a
  conversation process, reading one NDJSON user message per line from stdin.

For streaming input, send and flush a message such as:

```json
{"event":"user","message":{"content":"<prompt contents>"}}
```

Do not also supply `-p`: the documentation says command-line prompts are ignored
in streaming-input mode. Streaming input requires streaming output.

The documentation explicitly says the session stays open until stdin closes.
Closing stdin allows the process to exit after the current turn finishes.
Output includes `init`, `step_update`, and `result` events. A `result` describes
a turn, not an explicitly documented aggregate completion of all descendants.
Subagent spawn events can carry `subagent_info.subagents` conversation IDs.

Subagents run asynchronously. An idle subagent has sent a result to its parent
and can subsequently be awakened by another message.

The `Stop` hook exposes `fullyIdle`, documented as true when the agent is
finished and background commands or asynchronous tasks have completed. Its
behavior for nested subagents and its availability in the installed CLI have
**not** been tested. No hook was installed during this investigation.

There is a documentation/version discrepancy: the web page listed a five-minute
default print timeout, while installed help described `--print-timeout 0` as
waiting until the turn completes. The probe explicitly passed `0` and enforced
its own observation deadline. The installed CLI version was not recorded.

## Live Test and Evidence

Exactly one live AGY run was performed, using the original
[one-minute prompt](../tests/test_prompt.txt). No repeated status prompts were
sent, and no permission rules or hook configuration were changed.

The initial diagnostic invoked:

```text
agy --input-format stream-json --output-format stream-json --print-timeout 0
```

It sent one user message, kept stdin open, and observed for 150 seconds.

Evidence is retained in
[the original JSONL capture](../scripts/diag_output_1789937819.jsonl).
Times below are UTC on 2026-09-20:

| Time | Observation |
| --- | --- |
| 20:54:29 | Probe spawned AGY and sent the user message. |
| 20:54:40 | Parent spawned the `Wait Timer` subagent. |
| 20:54:42 | Subagent scheduled a 60-second timer. |
| 20:55:42 | Timer fired and the subagent called `send_message` to its parent. |
| 20:55:44 | Subagent transcript recorded message delivery and completion. |
| 20:55:45 | Probe recorded a parent `SUCCESS` result reporting completion. |
| 20:56:59 | Observation deadline elapsed; probe closed stdin; AGY exited `0`. |

AGY's result reported `duration_seconds: 73.245220857`. This is its own duration
measurement, not total wall time from process spawn. The response contained both
the launch acknowledgement and the later statement that the subagent had
completed its one-minute wait and returned.

Conversation IDs:

- Parent: `5f458f9e-70b0-47b3-a31a-6cb76aa78a2e`
- Subagent: `e192cad5-cba3-4d6e-ab20-16d6e65db919`

The subagent transcript was inspected to corroborate actual timer completion
and notification, rather than relying only on the parent's natural-language
claim. On the test machine it is located at:

```text
/home/vscode/.gemini/antigravity-cli/brain/e192cad5-cba3-4d6e-ab20-16d6e65db919/.system_generated/logs/transcript.jsonl
```

The original capture used a buffered text reader with selectors. This can delay
receipt timestamps for already-buffered lines. Do not treat those timestamps
as exact event-generation times. The transcript timestamps and AGY's reported
duration provide independent evidence. The current probe fixes the reader, but
was validated offline only; it did not generate the original capture.

## Diagnostic Artifacts

- [Reusable probe](../scripts/diag_agy_probe.py)
- [Offline fake-process tests](../tests/test_diag_agy_probe.py)
- [Original capture](../scripts/diag_output_1789937819.jsonl)

Run from the repository root, when another live run is authorized:

```bash
.venv/bin/python scripts/diag_agy_probe.py \
  --prompt-file tests/test_prompt.txt --timeout 150
```

The current probe uses binary pipes and selectors, records monotonic elapsed
times, and keeps stdin open for the observation window. It drains output during
shutdown and escalates from EOF to SIGINT and SIGKILL with bounded waits.
It targets the repository's Linux/macOS environment.

Logs default to a mode-0600 temporary file outside the repository. An explicit
`--output` path must not already exist. Tool arguments, tool results, and stderr
text are omitted, but response text remains: use only non-sensitive diagnostic
prompts. The original capture used a different key-based redaction scheme and
includes more detail; review it before publishing or committing it.

The observation deadline is not a success criterion. Likewise, the probe's exit
code reflects the child process, not verified completion of every task. This is
a diagnostic, not production supervision code ready to copy wholesale.

Validation after cleanup: all 10 repository tests passed; the three focused
diagnostic tests passed again after the final import adjustment; Pylint across
`src`, `tests`, and the probe scored 10/10; editor diagnostics were clear for the
new Python files. Tests cover partial-line handling, stdin lifetime, output after
EOF, early process failure, and event filtering. Forced shutdown and nested
subagent completion still need dedicated coverage.

The original prompt was accidentally modified by an early delegated test and
then restored exactly. Final tests use temporary fixtures. Production code and
the original prompt have no changes from this investigation.

## Recommended Next Steps (original plan — items 1-3 and 6 are now done)

1. ~~Change the production transport to streaming input/output.~~ Done: see
   `runner.py` above.
2. ~~Read NDJSON continuously without blocking on partial lines.~~ Done:
   `runner.py`'s `_run_turn`/`_consume_lines` use a selector-driven byte buffer.
3. ~~Establish an explicit completion rule before deciding when to close
   stdin.~~ Done via the `fullyIdle` Stop hook wait, with a grace-period
   fallback when the hook is absent. Still only validated against one
   subagent topology (see Known Caveats above) — multiple concurrent
   subagents and deep nesting remain unverified.
4. `Stop.fullyIdle` has now been used, per the reasoning above: it is the
   observe-only signal, never forcing `"decision": "continue"`, so it cannot
   itself waste model turns.
5. Preserve the wrapper's overall timeout, interrupt handling, and settings
   transaction lifetime. Keep temporary permissions until confirmed completion
   or complete shutdown. Unexpected EOF, missing completion evidence, protocol
   errors, and unsuccessful result statuses must not silently become success.
   *(Still true going forward — not separately re-verified in this pass beyond
   the existing `SettingsTransaction`/timeout tests.)*
6. ~~Add deterministic fake-AGY tests before another paid run.~~ Done: see
   `tests/test_runner.py` and `tests/test_agy_stop_signal_hook.py`.

Do not substitute fixed delays, silence windows, repeated natural-language
status polling, or process exit `0` for completion evidence. Do not add a
dependency or migrate to an SDK merely to fix this transport mismatch.

The acceptance criterion for a future live test is an observed child completion
followed by the parent's final response, with no premature exit and no leaked
processes. A run lasting more than 60 seconds is not enough on its own. The
third live validation run above met this criterion for a single subagent.

## Validation Commands

Use the repository virtual environment and keep checks focused before broad
validation:

```bash
.venv/bin/python -m unittest discover -s tests -p test_diag_agy_probe.py -v
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pylint src tests scripts/diag_agy_probe.py
markdownlint-cli2 --fix "**/*.md"
markdownlint-cli2 "**/*.md"
```

Inspect editor/Pylance diagnostics after Python changes. No new live AGY run is
needed merely to revalidate Markdown or the offline probe tests.
