# Integration Templates

Copy one of these snippets into your agent workspace instructions after
installing `task-skill-router`.

The important ordering is:

```text
understand request -> decompose tasks -> route tasks -> use/recommend skills
```

Do not run the router on the raw user request as the first step. A single user
request often decomposes into tasks that need different skills.

## Codex `AGENTS.md`

````markdown
## Task Skill Router

For non-trivial terminal coding tasks:

1. First understand the user's request and decompose it into concrete execution
   tasks.
2. Route the decomposed tasks before execution:

```bash
printf '%s\n' "<task 1>" "<task 2>" "<task 3>" | task-skill-router --batch
```

3. For each task, follow `routing` first and treat `matches` as supporting
   evidence:
   - `P0 recommend`: report the risk and confirm before destructive or sensitive
     actions.
   - `P1 auto-load` / `auto-run`: use the top installed match silently.
   - `P2 optional-load` / `guidance-only`: use only if it changes execution.
   - `P3 bypass`: do not load a skill.
   - Missing installed skills may be surfaced when they materially improve the
     task.
4. After execution, run normal verification before claiming completion.
5. Keep routing metadata out of the user-facing reply unless
   `routing.report_policy` is `report`, a missing skill blocks better execution,
   or the user asks why a skill was used.
6. When useful, record recommendations for later local review:

```bash
printf '%s\n' "<task 1>" "<task 2>" | task-skill-router --batch --record
```
````

## Claude Code `CLAUDE.md`

````markdown
## Task Skill Router

Before using skills on a non-trivial task:

1. Understand the user request.
2. Decompose it into execution tasks.
3. Run the router on those tasks:

```bash
printf '%s\n' "<task 1>" "<task 2>" "<task 3>" | task-skill-router --batch
```

4. Follow `routing.priority` and `routing.decision`; do not invent separate
   confidence thresholds in the agent prompt.
5. If a useful skill is missing, surface the install recommendation instead of
   silently continuing with a weaker workflow.
6. Treat high-risk tasks involving auth, secrets, config, deploys, deletes, or
   destructive operations as `recommend` even if a skill suggests automation.
7. Keep routing metadata silent unless the router asks for `report` or the user
   asks why a skill was used.
````

## Generic Terminal Agent

Use this when the agent supports shell commands or workspace-level rules:

````markdown
## Post-Decomposition Skill Routing

For complex requests, do not choose skills directly from the raw prompt.

1. Make a short task decomposition.
2. Pipe one task per line into `task-skill-router --batch`.
3. Follow the returned `routing` JSON to choose installed skills.
4. Surface missing skills as optional efficiency improvements.
5. Keep all routing local; do not upload task text or skill metadata.
6. Do not mention routing metadata in normal replies unless it changes what the
   user must decide.

```bash
printf '%s\n' "$TASK_1" "$TASK_2" "$TASK_3" | task-skill-router --batch
```
````

## Manual Mode

Use this for tools that cannot run shell commands:

1. Ask the agent to decompose the request into execution tasks.
2. Copy each task into a local terminal:

```bash
task-skill-router "inspect failing tests and identify root cause"
```

3. Paste the recommended installed skill or missing-skill hint back into the
   agent.

## Review Recommendation Hit Rate

If you enable local audit recording, periodically ask another skill, another
agent, or a stronger model to review pending recommendations:

```bash
task-skill-router --pending-reviews --limit 20
task-skill-router --review rec_xxxxx --judgment hit --evaluator agent:reviewer
task-skill-router --stats
```

Audit records are local JSONL files. They are meant to help tune your own skill
metadata and community mappings, not to send telemetry to this project.
