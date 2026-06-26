# Changelog

## Unreleased

### Changed

- Added priority routing output (`P0`/`P1`/`P2`/`P3`) so agents can follow a
  compact decision surface instead of interpreting raw match scores.
- Added answer-only/simple-check bypass routing to reduce unnecessary skill
  loading ceremony.
- Added small workflow-intent boosts for root-cause debugging and
  frontend/design tasks so production workflows route to the right skills more
  reliably.
- Expanded default skill directories to include Codex, Claude, Agents, and
  Hermes skill libraries.
- Updated integration guidance to keep routing metadata silent unless it affects
  user choice.

## v0.1.0 (2026-06-11)

Initial public release.

### Features

- **Task routing**: Route decomposed execution tasks to matching `SKILL.md` workflows using TF-IDF cosine similarity on skill frontmatter metadata.
- **Single-task mode**: `task-skill-router "your task text"` returns ranked JSON matches.
- **Batch mode**: `printf '%s\n' "task1" "task2" | task-skill-router --batch` routes multiple tasks at once.
- **Missing-skill detection**: Community mappings (`config/community.yaml`) surface useful skills that are not installed locally, with install hints.
- **Hit-rate auditing**: Local JSONL audit log records recommendation events for later review.
- **Review workflow**: `--pending-reviews`, `--review`, `--judgment`, `--stats` support multi-agent or human-in-the-loop evaluation of routing quality.
- **Auto-run vs recommend modes**: High-risk tasks are forced to `recommend` mode; low-risk tasks can use `auto-run`.
- **TF-IDF indexing**: Pure Python implementation, no external ML dependencies.

### Installers

- macOS: `install-macos.sh` — places executable, command shim, and default config.
- Linux: `install-linux.sh` — same layout as macOS.
- Windows PowerShell: `install-windows.ps1` — places executable and adds `%USERPROFILE%\.local\bin` to PATH.
- Generic POSIX: `install.sh` — for WSL, Git Bash, and other POSIX-like shells.

### Documentation

- README with runnable Quick Demo using synthetic `examples/` fixtures.
- Agent integration templates in `docs/integration-templates.md` for Codex (`AGENTS.md`), Claude Code (`CLAUDE.md`), and custom terminal agents.
- `CONTRIBUTING.md` with community mapping guidelines.
- `PRIVACY.md` stating the local-first, no-telemetry design.
- `SECURITY.md` for vulnerability reporting.

### Configuration

- `config/config.yaml` with `skills_dirs`, `community_mapping`, `confidence_threshold`, `max_matches`, `preferred_skills`, and `mode_overrides`.
- Environment variable overrides for all config values.
- `config/community.yaml` for mapping common task wording to skill names.

### Assets

- `assets/demo-routing.svg`: Sanitized terminal-style demo showing three decomposed tasks routed to installed skills and one missing-skill recommendation.

### Testing & CI

- 8 unit tests covering indexing, matching, batch mode, audit recording, review workflow, and stats.
- Cross-platform CI: macOS, Linux, Windows (PowerShell syntax check).
- Shell syntax validation for all shell/PowerShell installers.
- Code quality: `py_compile` on main script, `unittest` on tests.
