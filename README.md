# sdlc-pipeline

An autonomous SDLC orchestrator plugin for Claude Code, Claude Cowork, and Cursor. One command — `/pipeline` — takes a feature or bug from raw request to shipped PR through planning, review gauntlets, TDD execution, testing gates, security review, docs, and ship.

Built on top of **superpowers**, **gstack**, and **claude-mem** — all three are required and must be installed first (see [Prerequisites](#prerequisites)).

## What's inside

| Component | Count | Purpose |
|---|---|---|
| Commands | 1 | `/pipeline` — the end-to-end orchestrator |
| Agents | 14 | Specialist sub-agents: planner, investigator, implementer, reviewers (code, security, eng, design, CEO, perf), unit-tester, qa-tester, adr-writer, doc-writer, ship-pr |
| Hooks | 2 | Token tracking and per-run token reports |
| Scripts | 2 | `check_plan.py` plan linter; `detect_stack.py` stack profile (Flutter/Dart) |

The orchestrator never writes production code itself. It classifies your request, dispatches specialist agents, enforces quality gates, and only interrupts you for genuine decisions.

## Prerequisites

This plugin dispatches skills from three other dependencies. All are **required** — `/pipeline` halts at preflight if any is missing. Install them **before** installing sdlc-pipeline:

### Python 3

The bundled hooks (`guard_context_budget.py`, `check_plan.py`) are Python scripts invoked by Claude at runtime. **Python 3.8+** must be available on your `PATH` before the hooks will run:

```bash
# verify
python3 --version   # should print Python 3.8 or later
```

If `python3` is not found, install it from [python.org/downloads](https://www.python.org/downloads/) or via your package manager:

```bash
# macOS (Homebrew)
brew install python

# Ubuntu / Debian
sudo apt install python3

# Windows (winget)
winget install Python.Python.3
```

> [!IMPORTANT]
> ⚠️ 5-minute prompt cache active. Set `ENABLE_PROMPT_CACHING_1H=1` and restart for ~25% lower cost.

### Plugin dependencies

1. **superpowers** — provides `brainstorming`, `writing-plans`, `executing-plans`, `test-driven-development`, and more.
   ```
   /plugin marketplace add obra/superpowers-marketplace
   /plugin install superpowers@superpowers-marketplace
   ```
2. **gstack** — provides `/office-hours`, `/spec`, and `/ship` used by the planning and ship stages. Installs via git clone + setup script (not a plugin marketplace) — see [garrytan/gstack](https://github.com/garrytan/gstack):
   ```
   git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git ~/.claude/skills/gstack
   cd ~/.claude/skills/gstack && ./setup
   ```
3. **claude-mem** — persistent memory across sessions; captures session context and injects it back into future runs.
   ```
   /plugin marketplace add thedotmack/claude-mem
   /plugin install claude-mem
   ```

If your team distributes plugins centrally, some may already be pre-installed — check with `/plugin` (and `~/.claude/skills/gstack` for gstack) before adding them.

## Installation

### Claude Code (CLI)

1. Add this repo as a marketplace:
   ```
   /plugin marketplace add ilyasarafathemvigo/flutter-sdlc-pipeline
   ```
2. Install the plugin:
   ```
   /plugin install sdlc-pipeline@sdlc-pipeline-dev
   ```
3. Restart Claude Code (or run `/reload-plugins` during development).
4. Verify: type `/` and confirm `/pipeline` appears.

### Claude Cowork / Claude Desktop

1. Open the **Customize** menu in the left sidebar, then the **Plugins** tab.
2. In **Personal plugins**, click **+** → **Add marketplace** → **Add from a repository**.
3. Paste: `https://github.com/ilyasarafathemvigo/flutter-sdlc-pipeline`
4. Once the marketplace syncs, click **Install** on **sdlc-pipeline**.
5. Start a new conversation for the plugin to take effect.

Note: hooks and sub-agents run in Cowork and Claude Code; in plain chat only skills are available.

### Cursor

1. Open Cursor **Settings** → **Plugins** (or **Rules & Memories → Plugins**, depending on version).
2. Click **Add Plugin** → **From Git repository**.
3. Paste: `https://github.com/ilyasarafathemvigo/flutter-sdlc-pipeline`
4. Cursor reads `.cursor-plugin/plugin.json` and installs the plugin.
5. Reload the Cursor window (`Cmd/Ctrl+Shift+P` → "Reload Window").

Alternatively, clone the repo and copy `agents/` and `commands/` into your project's `.cursor/` directory if your Cursor version doesn't support Git plugin installs.

### Updating

Marketplace installs don't auto-pull new commits. To get the latest version:

- **Claude Code:** `/plugin marketplace update sdlc-pipeline-dev`
- **Cowork/Desktop:** Customize → Plugins → find the marketplace → ⋯ menu → **Update**, then start a new session.

## Usage

### Example 1 — build a feature

```
/pipeline Add CSV export to the reports page
```

What happens, step by step:

1. **Classify** — the orchestrator sizes the request (nano vs full run).
2. **Preferences** — you're asked three plain-language questions: bug or feature? test-first development? dedicated unit-test round?
3. **Plan** — the `planner` agent drafts an executable plan using superpowers `brainstorming`/`writing-plans` and gstack `/office-hours`/`/spec`.
4. **Plan review gauntlet** — `eng-reviewer`, `design-reviewer`, and `ceo-reviewer` review the plan in parallel.
5. **Your approval** — hard gate. No code is written until you approve the plan.
6. **Execute** — `implementer` agents build each task on a dedicated branch, test-first if you opted in.
7. **Quality gates** — `unit-tester` audits coverage, `qa-tester` walks acceptance scenarios, then `code-reviewer` and `security-reviewer` (OWASP + STRIDE) run in parallel.
8. **Docs & ship** — `doc-writer` updates documentation, then `ship-pr` verifies all sign-offs and ships via gstack `/ship`.

### Example 2 — fix a bug

```
/pipeline Login button does nothing after session timeout
```

Bugs skip the planner: the `investigator` agent does root-cause analysis and produces a mini-plan in `docs/bugs/`, then the pipeline proceeds to execution and the same review gates.

### Example 3 — tiny change (nano tier)

```
/pipeline Fix the typo in the welcome banner
```

Nano changes skip planning and reviews entirely: `implementer` → `code-reviewer` → `ship-pr`. Fast path, still reviewed.

## Flutter & Dart projects

`/pipeline` and `/pipeline-parallel` detect a Flutter or Dart repo automatically. Nothing changes for other stacks.

At Stage 0, `scripts/detect_stack.py` reads `pubspec.yaml` and the repo layout and writes a **stack profile** to `.pipeline-stack.md`, which is git-excluded. The profile records the toolchain (including FVM pins), platforms, flavors, state management, routing, codegen, localisation, storage, test setup, the exact format/analyze/codegen/test commands, and which files are never parallel-safe. The planner copies the profile into the plan's Global Constraints, so every implementer gets the right commands without opening the manifest.

What changes on a Flutter/Dart stack:

| Stage | Flutter behaviour |
|---|---|
| Preflight (Stage 0) | Halts if `flutter`/`dart` (or `fvm`) is not on `PATH` |
| Plan | One task owns `pubspec.yaml`; codegen tasks are flagged `codegen: true`; platform files (AndroidManifest, Info.plist) and local-DB migrations are explicit; tests are written as unit, `testWidgets`, golden and `integration_test` cases |
| Plan lint | Recognises drift, sqflite, Hive, Isar, shared_preferences and secure-storage idioms; flags manifest-editing or codegen tasks marked `parallel-safe: true` |
| Execute | Runs `pub get`, `build_runner` and `gen-l10n` when needed; never hand-edits generated files; never runs `--update-goldens` just to get a test green |
| Unit-test gate | Runs `flutter test --coverage` and checks changed-line coverage against `lcov.info` |
| QA gate | Drives scenarios with `integration_test` on a device, emulator or desktop target, and falls back to widget-level checks (clearly labelled); uses `/browse` only for web targets |
| Code / security review | Flutter lens (async `BuildContext`, disposal, rebuild cost) plus OWASP MASVS (secrets in the binary, insecure storage, cleartext traffic, deep links, exported components) |
| Perf gate | Profile-mode frame timings, startup trace and `--analyze-size` instead of web benchmarks |
| Ship | Compile-only build for each declared platform before the PR; version stays in `pubspec.yaml` |

Generated Dart files (`*.g.dart`, `*.freezed.dart`, `*.gr.dart`, `*.mocks.dart`, `*.config.dart`, `app_localizations*.dart`) are left out of review diffs.

Requirements: the Flutter SDK (or FVM) on `PATH`. A running emulator, simulator or desktop target lets the QA gate walk scenarios end to end. Without one, the QA gate reports reduced evidence and never a silent pass.

## Workflow

```
request
   │
   ▼
Stage 0    Classify (nano fast-path ─────────────────────┐)
Stage 0.5  Your preferences: bug/feature, TDD, unit tests │
   │                                                      │
   ├── FEATURE ──► Stage 1  Plan (planner)                │
   │               Stage 2  Plan reviews ∥ (eng/design/ceo)
   │               Stage 2.5  ★ YOU APPROVE THE PLAN ★    │
   │               Stage 2.7  ADR (if architecture changes)
   │                                                      │
   └── BUG ──────► Stage 1-B  Investigate (root cause)    │
   │                                                      │
   ▼                                                      │
Stage 3    Execute on dedicated branch (TDD if on) ◄──────┘
Stage 4    Unit-test gate (if opted in)
Stage 4.5  QA scenario gate (if user-facing)
Stage 5    Code review ∥ Security review (OWASP + STRIDE)
Stage 5.5  Performance gate (only if perf-sensitive)
Stage 5.8  Documentation
Stage 6    Ship PR (via gstack /ship)
```

`∥` = stages run in parallel. Token usage is tracked per run by the bundled hooks.

## Hard rules the pipeline enforces

- No production code before you approve the plan (Stage 2.5 is a hard gate).
- The orchestrator never writes code — only specialist agents do.
- Reviewers are read-only and report-only; they never "fix things while they're in there".
- Implementers run one at a time (they share the working tree); reviewers run in parallel.

## License

MIT — free to use, modify, and distribute. See [`LICENSE`](LICENSE).
