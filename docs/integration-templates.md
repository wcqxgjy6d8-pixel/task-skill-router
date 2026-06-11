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

3. For each task, inspect the JSON result:
   - If the top match is installed and mode is `auto-load` or `recommend`, read
     the referenced `SKILL.md` before executing that task.
   - If the top match is not installed, tell the user which skill is missing and
     why it would improve the task.
   - If `high_risk` is true, recommend the skill and explain the risk before
     taking destructive or sensitive actions.
4. After execution, run normal verification before claiming completion.
5. When useful, record recommendations for later local review:

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

4. Use installed `SKILL.md` recommendations when confidence is high enough for
   the task.
5. If a useful skill is missing, surface the install recommendation instead of
   silently continuing with a weaker workflow.
6. Treat high-risk tasks involving auth, secrets, config, deploys, deletes, or
   destructive operations as `recommend` even if a skill suggests automation.
````

## Generic Terminal Agent

Use this when the agent supports shell commands or workspace-level rules:

````markdown
## Post-Decomposition Skill Routing

For complex requests, do not choose skills directly from the raw prompt.

1. Make a short task decomposition.
2. Pipe one task per line into `task-skill-router --batch`.
3. Use the returned JSON to choose installed skills.
4. Surface missing skills as optional efficiency improvements.
5. Keep all routing local; do not upload task text or skill metadata.

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
