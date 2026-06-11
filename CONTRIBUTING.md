# Contributing

task-skill-router is intentionally small. Keep changes boring, testable, and easy
to inspect.

## Local Checks

```bash
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests
```

## Community Mappings

Add common task wording to `config/community.yaml` when a skill's own
frontmatter is too sparse for good matching.

Each entry uses this shape:

```yaml
skills:
  skill-name:
    description: "One or two sentences describing when to use the skill"
    tags: ["keyword", "phrase", "domain"]
    mode: "recommend"
```

Use `recommend` for any skill that can touch auth, config, secrets, deploys, or
destructive operations.

## Pull Requests

- Include a failing or regression test for router behavior changes.
- Keep new dependencies out unless they clearly improve routing quality.
- Do not include private skill paths, credentials, tokens, or local agent state.
