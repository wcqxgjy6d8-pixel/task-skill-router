# Promotion Notes

Use transparent, opt-in promotion only. Do not buy stars, automate engagement,
spam communities, impersonate users, or post private screenshots/logs.

## One-Sentence Positioning

task-skill-router is a post-decomposition `SKILL.md` router for terminal coding
agents: plan first, route each execution task to the right skill, and surface
missing useful skills.

## Short Post Draft

I open-sourced `task-skill-router`, a small CLI for Codex, Claude Code, OpenCode,
and other terminal coding agents.

The pattern is:

1. Let the agent understand and decompose the request.
2. Route each execution task to matching local `SKILL.md` workflows.
3. Surface useful skills that are not installed yet.
4. Optionally record local JSONL audit events so another agent/model can review
   whether the recommendation was a hit, partial hit, or miss.

It is not a skill registry, not a Claude-only meta-skill, and not a full agent
orchestrator. It is the small layer between planning and execution.

Repo: https://github.com/wcqxgjy6d8-pixel/task-skill-router

## Communities To Consider

- GitHub topic discovery: `ai-agents`, `codex`, `claude-code`, `developer-tools`
- Claude Code / Codex user communities where self-promotion is allowed
- Personal technical blog post with concrete examples
- Project README badges and release notes before broader posting

## Privacy Checklist Before Posting

- No local absolute paths except generic examples like `/Users/me/...`
- No screenshots containing private repos, usernames, tokens, prompts, memories,
  or terminal history
- No claims about benchmarks that were not measured
- No automated direct messages
- No fake usage stats
