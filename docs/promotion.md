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

## Launch Assets

### Social Short

Open-sourced `task-skill-router`: a local-first CLI that helps terminal coding
agents route decomposed tasks to the right `SKILL.md` workflow.

It is meant to run after planning, not before it:

1. decompose the request
2. route each execution task
3. surface missing useful skills
4. optionally audit recommendation hit rate locally

Works with Codex, Claude Code, OpenCode, and custom terminal agents.

https://github.com/wcqxgjy6d8-pixel/task-skill-router

### Developer Forum Draft

I built `task-skill-router` for a workflow problem I kept seeing in terminal
coding agents: once you have many slash commands or `SKILL.md` workflows, the
agent needs a small routing step after it decomposes the user request.

The CLI scans configured `SKILL.md` directories, builds a pure-Python TF-IDF
index from skill metadata, and returns ranked JSON for each execution task. It
also supports community mappings for missing skills and a local JSONL audit log
so another agent/model can later judge whether a recommendation was a hit,
partial hit, or miss.

It is intentionally not a full orchestrator. The intended flow is:

```text
user request -> agent planning -> decomposed tasks -> task-skill-router -> skill execution
```

The project is local-first: no telemetry, no background service, no maintainer
data collection.

Repo: https://github.com/wcqxgjy6d8-pixel/task-skill-router

### Blog Outline

Title: "A tiny post-planning skill router for terminal coding agents"

- Problem: terminal agents accumulate too many commands, skills, and workflow
  files for humans or agents to remember reliably.
- Key design choice: route after task decomposition, because one user request
  often needs several different skills.
- Implementation: scan `SKILL.md` frontmatter, enrich with optional community
  mappings, rank tasks with TF-IDF, emit JSON.
- Missing-skill detection: recommend useful skills that are not installed.
- Hit-rate auditing: local JSONL records reviewed by another skill, another
  agent, or a stronger model.
- Boundaries: heuristic router, not calibrated probability, not an autopilot,
  not a registry, not tied to one vendor.
- Demo: run the synthetic `examples/` fixture from the README.

## Demo Asset Plan

Create only sanitized assets from the repository fixture:

- Use `examples/demo-config.yaml`, not private local skills.
- Record a terminal GIF or screenshot of the README Quick Demo.
- Show three tasks: failing tests, docs update, research papers.
- Show the missing `arxiv` hint as the main differentiator.
- Crop out shell history, username, hostname, private paths, and unrelated tabs.
- Do not claim measured adoption, benchmarks, or star growth in the image.

Suggested caption:

```text
The interesting bit is not "one more agent router". It routes after planning,
so each decomposed task can get a different skill, and it can tell the user
which useful skill is missing before execution quality suffers.
```

## Communities To Consider

- GitHub topic discovery: `ai-agents`, `codex`, `claude-code`, `developer-tools`
- Claude Code / Codex user communities where self-promotion is allowed
- Personal technical blog post with concrete examples
- Project README badges and release notes before broader posting
- Hacker News "Show HN" only if the README demo and install path are stable
- Reddit or Discord only in channels that explicitly allow project sharing

## Promotion Sequence

1. Keep CI green on `main`.
2. Make the README demo copy-paste runnable from a fresh clone.
3. Publish a small release note when the demo, installers, and docs are stable.
4. Share the short social post from a personal account.
5. Share the developer forum draft only in communities that allow launch posts.
6. Reply to questions with technical details, not repeated star requests.
7. Convert recurring questions into README or issue-template improvements.

Ask for a star only as a light opt-in line, for example:

```text
If this fits your agent workflow, a GitHub star helps other terminal-agent users find it.
```

## Privacy Checklist Before Posting

- No local absolute paths except generic examples like `/Users/me/...`
- No screenshots containing private repos, usernames, tokens, prompts, memories,
  or terminal history
- No claims about benchmarks that were not measured
- No automated direct messages
- No fake usage stats

## Prohibited Growth Tactics

- Buying stars, asking for star exchanges, or using engagement pods
- Automated comments, issues, pull requests, emails, DMs, or mentions
- Posting the same message repeatedly across unrelated communities
- Impersonating users, maintainers, companies, or AI tools
- Scraping private communities or personal data for outreach
- Publishing private local configs, prompts, agent memories, tokens, or logs
- Claiming compatibility, adoption, benchmarks, or security guarantees that have
  not been verified
