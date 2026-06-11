# Examples

This directory contains synthetic demo skills and config. They are safe to use
for a quick local test without installing real Codex or Claude Code skills.

Run from the repository root:

```bash
printf '%s\n' \
  "inspect failing tests and identify root cause" \
  "update README usage docs" \
  "search research papers for related work" \
  | TASK_SKILL_ROUTER_CONFIG=examples/demo-config.yaml python3 task-skill-router.py --batch
```

Expected behavior:

- `systematic-debugging` matches the failing-tests task
- `docs` matches the README task
- `arxiv` appears as a missing useful skill from `demo-community.yaml`
