---
name: task-skill-router
description: "Post-decomposition skill router for terminal coding agents. After decomposing a task, route each execution unit to the best SKILL.md workflow and surface missing useful skills."
tags: ["routing", "task decomposition", "skill matching", "terminal", "coding agent", "recommender"]
---

# Task Skill Router Protocol

Use this after understanding the user's request and decomposing it into concrete
execution tasks.

The goal is simple: do not guess which slash command, workflow, or skill should
handle each subtask. Plan first, route each execution unit, then load the right
`SKILL.md`.

## Protocol

1. Understand the request.
2. Decompose it into concrete execution tasks.
3. Run task-skill-router on the decomposed tasks.
4. Load installed skills for execution.
5. Surface missing useful skills to the user.

For one task:

```bash
task-skill-router "<decomposed execution task>"
```

For multiple tasks:

```bash
printf '%s\n' \
  "<task 1>" \
  "<task 2>" \
  "<task 3>" \
  | task-skill-router --batch
```

If `task-skill-router` is not on `PATH`, use:

```bash
python3 ~/.task-skill-router/task-skill-router.py "<decomposed execution task>"
```

## Router Output

Each match includes:

- `skill`: matched skill name
- `installed`: whether the skill exists locally
- `path`: path to the matched `SKILL.md`, if installed
- `confidence`: TF-IDF cosine similarity score
- `mode`: suggested handling mode
- `reason`: why the skill matched
- `install_hint`: how to install or add the skill when missing

Batch output also includes top-level `missing_skills`.

## What To Do With The Result

| Case | Behavior |
| --- | --- |
| `installed: true` and `auto-load` | Load the matched `SKILL.md` and follow its workflow. |
| `installed: true` and `recommend` | Tell the user the recommended skill and why before proceeding. |
| `installed: false` | Tell the user the useful skill is missing and show the install hint. |
| `auto-run` | Only run deterministic, low-risk commands explicitly provided by the mapping. |

High-risk tasks involving auth, secrets, config, deploys, deletes, or destructive
operations must stay in `recommend` mode.

## Red Lines

| Don't | Do |
| --- | --- |
| Run router before understanding the request | Decompose first, then route subtasks |
| Route only the original large request | Route each execution unit |
| Guess from memory | Use the router result |
| Treat confidence as probability | Treat it as a ranking score |
| Ignore missing skills | Tell the user what skill would help |
| Auto-run risky workflows | Ask before auth/config/deploy/delete work |
| Use stale copied skill text | Load the current `SKILL.md` from `path` |
| Trust completion claims | Verify with tests, build, or direct checks |

## Integration Notes

This protocol works best for terminal-first tools such as Codex CLI, Claude
Code, OpenCode, and custom agents because they can run shell commands and read
workspace instructions.

It does not require patching the agent's source code. Source-level integration
is stronger, but a project instruction file such as `AGENTS.md`, `CLAUDE.md`, or
another workspace rule file is usually enough for soft integration.
