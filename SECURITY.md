# Security Policy

## Supported Versions

Security reports should target the latest release and the `main` branch.

## Reporting a Vulnerability

Please open a GitHub security advisory if available, or create a minimal issue
that avoids exposing secrets. Do not include tokens, passwords, private keys,
private repository contents, or unredacted audit logs.

## Scope

Relevant security issues include:

- command injection in installers or generated command shims
- unsafe handling of local paths
- accidental network transmission of task text or audit logs
- unsafe defaults that could leak private skill metadata

Out of scope:

- malicious third-party skills installed by a user
- incorrect skill recommendations that do not create a security boundary issue
- prompts or examples that require intentionally pasting secrets into an issue

## Design Notes

task-skill-router is designed to be local-first:

- no telemetry
- no background service
- no maintainer-controlled network endpoint
- audit logs are opt-in and local JSONL files
