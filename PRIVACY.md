# Privacy

task-skill-router is a local CLI tool. It does not send task text, skill names,
paths, audit logs, or configuration to this project or to any hosted service.

## Local Files

By default, the tool reads:

- configured local `SKILL.md` directories
- `~/.config/task-skill-router/config.yaml`
- `~/.config/task-skill-router/community.yaml`

When `--record` is used, it writes local audit events to:

```text
~/.task-skill-router/audit/events.jsonl
```

Audit events can contain task text and recommended skill names. Treat this file
as local user data. Do not paste it into issues unless you have reviewed and
redacted it.

## Network Use

The router itself does not make network requests. The installer scripts use
GitHub raw URLs only to download project files.

## Telemetry

There is no telemetry, analytics, background service, or maintainer-controlled
data collection.

## Safe Issue Reports

When reporting bugs, prefer small synthetic examples. Do not include private
repository names, tokens, auth state, local agent memory, private task prompts,
or unredacted absolute paths.
