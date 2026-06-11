#!/usr/bin/env python3
"""
task-skill-router — Generic task-to-skill recommender for coding agents.

Scans SKILL.md libraries, builds a TF-IDF index from their frontmatter
(name, description, tags), and matches decomposed execution tasks to relevant
skills. Designed to run after task decomposition and before execution.

Usage:
    task-skill-router "修 bug，測試失敗，要找根因並修復"
    task-skill-router "redesign the landing page UI"
    task-skill-router "check GitHub PR, do code review"
    printf '%s\n' "inspect failing test" "patch root cause" | task-skill-router --batch

Exit code:
    0 — matches found
    1 — no matches
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import yaml as _yaml
except ImportError:  # pragma: no cover - exercised only without PyYAML installed
    _yaml = None


# ──────────────────────────────────────────────
#  Defaults
# ──────────────────────────────────────────────
DEFAULT_SKILLS_DIR = "~/.task-skill-router/skills"
DEFAULT_CONFIG_PATH = "~/.config/task-skill-router/config.yaml"
DEFAULT_COMMUNITY_PATH = ""
MAX_MATCHES = 5
CONFIDENCE_THRESHOLD = 0.12
VALID_MODES = {"auto-load", "auto-run", "recommend"}

HIGH_RISK_PATTERNS = [
    r"config\b", r"\.env", r"auth", r"delete", r"remove", r"rm\s",
    r"push\s+--force", r"deploy", r"cert", r"entitlement",
    r"API\s*key", r"secret", r"password", r"token",
]


# ──────────────────────────────────────────────
#  YAML loading
# ──────────────────────────────────────────────

def strip_inline_comment(value: str) -> str:
    """Remove unquoted YAML comments from a scalar value."""
    quote: str | None = None
    escaped = False
    for i, ch in enumerate(value):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            continue
        if ch == "#" and (i == 0 or value[i - 1].isspace()):
            return value[:i].rstrip()
    return value.strip()


def parse_scalar(value: str) -> Any:
    """Parse the small YAML scalar subset used by config and skill frontmatter."""
    value = strip_inline_comment(value.strip())
    if not value:
        return ""
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part.strip()) for part in inner.split(",")]
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.lower() in {"null", "none"}:
        return None
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """
    Parse a conservative YAML subset.

    PyYAML is used when available. This fallback is intentionally small but
    covers the frontmatter/config shapes this project ships: nested mappings,
    quoted scalars, inline lists, numbers, booleans, and literal blocks.
    """
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    lines = text.splitlines()
    i = 0

    while i < len(lines):
        raw = lines[i]
        i += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue

        indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()
        if ":" not in stripped:
            continue

        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if not key:
            continue

        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if raw_value in {"|", ">"}:
            block_lines: list[str] = []
            block_indent: int | None = None
            while i < len(lines):
                nxt = lines[i]
                if not nxt.strip():
                    block_lines.append("")
                    i += 1
                    continue
                nxt_indent = len(nxt) - len(nxt.lstrip(" "))
                if nxt_indent <= indent:
                    break
                if block_indent is None:
                    block_indent = nxt_indent
                block_lines.append(nxt[block_indent:])
                i += 1
            parent[key] = "\n".join(block_lines).strip()
            continue

        if raw_value == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
            continue

        parent[key] = parse_scalar(raw_value)

    return root


def load_yaml_text(text: str) -> dict[str, Any]:
    if _yaml is not None:
        data = _yaml.safe_load(text) or {}
    else:
        data = parse_simple_yaml(text)
    return data if isinstance(data, dict) else {}


def load_yaml_file(path: str | Path) -> dict[str, Any]:
    p = Path(path).expanduser()
    if not p.is_file():
        return {}
    try:
        return load_yaml_text(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ──────────────────────────────────────────────
#  Pure-Python TF-IDF
# ──────────────────────────────────────────────

TOKEN_ALIASES = {
    "fixed": "fix",
    "fixes": "fix",
    "fixing": "fix",
    "failing": "fail",
    "failed": "fail",
    "failures": "failure",
    "bugs": "bug",
    "tests": "test",
    "testing": "test",
    "authenticated": "auth",
    "authentication": "auth",
    "authorization": "auth",
}


def normalize_token(token: str) -> str:
    if token in TOKEN_ALIASES:
        return TOKEN_ALIASES[token]
    if len(token) > 4 and token.endswith("ies"):
        return f"{token[:-3]}y"
    if len(token) > 5 and token.endswith("ing"):
        return token[:-3]
    if len(token) > 4 and token.endswith("ed"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    """Split text into lowercase tokens, including CJK characters."""
    text = text.lower()
    tokens = re.findall(r"[a-z][a-z0-9]{1,}|[\u4e00-\u9fff]{1,4}", text)
    return [normalize_token(token) for token in tokens]


class TfidfIndex:
    """Minimal pure-Python TF-IDF vectorizer and index."""

    def __init__(self):
        self.doc_vectors: list[tuple[str, Counter]] = []  # (doc_id, tf_counter)
        self.idf: dict[str, float] = {}
        self.num_docs = 0
        self._built = False

    def add(self, doc_id: str, text: str) -> None:
        tokens = tokenize(text)
        if not tokens:
            return
        self.doc_vectors.append((doc_id, Counter(tokens)))
        self._built = False

    def build(self) -> None:
        n = len(self.doc_vectors)
        if n == 0:
            self._built = True
            return
        df: Counter[str] = Counter()
        for _, tf in self.doc_vectors:
            for token in tf:
                df[token] += 1
        self.idf = {tok: math.log((n + 1) / (cnt + 1)) + 1 for tok, cnt in df.items()}
        self.num_docs = n
        self._built = True

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        if not self._built:
            self.build()
        if self.num_docs == 0:
            return []

        q_tokens = tokenize(query)
        q_tf = Counter(q_tokens)
        q_norm = math.sqrt(sum(
            (q_tf[tok] * self.idf.get(tok, 0)) ** 2
            for tok in q_tf
        ))
        if q_norm == 0:
            return []

        scores: list[tuple[str, float]] = []
        for doc_id, tf in self.doc_vectors:
            dot = 0.0
            for tok in q_tf:
                if tok in tf:
                    dot += q_tf[tok] * self.idf.get(tok, 0) * tf[tok] * self.idf.get(tok, 0)
            doc_norm = math.sqrt(sum(
                (tf[tok] * self.idf.get(tok, 0)) ** 2
                for tok in tf
            ))
            if doc_norm > 0:
                sim = dot / (q_norm * doc_norm)
                if sim > 0:
                    scores.append((doc_id, sim))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


# ──────────────────────────────────────────────
#  Skill discovery
# ──────────────────────────────────────────────

def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if isinstance(value, tuple):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def skill_index_text(skill_name: str, meta: dict[str, Any]) -> str:
    tags = " ".join(as_list(meta.get("tags")))
    community_tags = " ".join(as_list(meta.get("community_tags")))
    return " ".join(
        part
        for part in [
            skill_name,
            str(meta.get("description", "")),
            str(meta.get("community_description", "")),
            tags,
            community_tags,
        ]
        if part
    )


def discover_skills(skills_dirs: str | list[str]) -> dict[str, dict[str, Any]]:
    """Scan directory for SKILL.md files, return {name: metadata}."""
    if isinstance(skills_dirs, str):
        roots = [
            Path(item).expanduser().resolve()
            for item in skills_dirs.split(os.pathsep)
            if item
        ]
    else:
        roots = [Path(item).expanduser().resolve() for item in skills_dirs]

    skills: dict[str, dict[str, Any]] = {}
    visited: set[str] = set()

    for root in roots:
        if not root.is_dir():
            continue

        for dirpath, dirnames, filenames in os.walk(str(root), followlinks=True):
            try:
                dir_real = os.path.realpath(dirpath)
            except OSError:
                dirnames.clear()
                continue
            if dir_real in visited:
                dirnames.clear()
                continue
            visited.add(dir_real)

            if "SKILL.md" not in filenames:
                continue
            sp = Path(dirpath) / "SKILL.md"
            try:
                content = sp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            m = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
            if not m:
                continue

            meta = load_yaml_text(m.group(1))
            skill_name = str(meta.get("name") or sp.parent.name).strip()
            if not skill_name or skill_name in skills:
                continue

            description = str(meta.get("description") or "").strip()
            tags = as_list(meta.get("tags"))

            skills[skill_name] = {
                "name": skill_name,
                "path": str(sp),
                "description": description,
                "tags": sorted(set(tags)),
                "dir": str(sp.parent),
            }

    return skills


# ──────────────────────────────────────────────
#  Community skill mapping
# ──────────────────────────────────────────────

def load_community_mapping(path: str) -> dict[str, dict[str, Any]]:
    """Load community-contributed skill mappings from YAML."""
    if not path:
        return {}
    data = load_yaml_file(path)
    skills = data.get("skills", {})
    if not isinstance(skills, dict):
        return {}
    return {
        str(name): mapping
        for name, mapping in skills.items()
        if isinstance(mapping, dict)
    }


# ──────────────────────────────────────────────
#  Risk detection
# ──────────────────────────────────────────────

def is_high_risk(task: str) -> bool:
    task_lower = task.lower()
    for pat in HIGH_RISK_PATTERNS:
        if re.search(pat, task_lower):
            return True
    return False


# ──────────────────────────────────────────────
#  Mode selection
# ──────────────────────────────────────────────

def select_mode(
    task: str,
    skill_name: str,
    confidence: float,
    config_overrides: dict[str, str] | None = None,
    suggested_mode: str | None = None,
) -> str:
    """
    Determine which mode to use for this match.

    Priority:
    1. High-risk task → always "recommend"
    2. Config override (user can set per-skill mode)
    3. Confidence-based default
    """
    if is_high_risk(task):
        return "recommend"

    # Check user config overrides
    if config_overrides and skill_name in config_overrides:
        override = config_overrides[skill_name]
        if override in VALID_MODES:
            return override

    if suggested_mode in VALID_MODES:
        return suggested_mode

    # Confidence-based fallback
    if confidence >= 0.65:
        return "auto-load"
    elif confidence >= 0.45:
        return "recommend"
    else:
        return "recommend"


# ──────────────────────────────────────────────
#  Main recommendation
# ──────────────────────────────────────────────

def recommend(
    task: str,
    skills_dir: str | None = None,
    config_path: str | None = None,
    community_path: str | None = None,
) -> dict[str, Any]:
    # Load user config
    resolved_config_path = (
        os.environ.get("TASK_SKILL_ROUTER_CONFIG")
        or os.environ.get("SKILL_ROUTER_CONFIG")
        or config_path
        or DEFAULT_CONFIG_PATH
    )
    config = load_yaml_file(resolved_config_path)

    resolved_skills_dirs = (
        os.environ.get("TASK_SKILL_ROUTER_DIR")
        or os.environ.get("SKILL_ROUTER_DIR")
        or skills_dir
        or config.get("skills_dirs")
        or config.get("skills_dir")
        or DEFAULT_SKILLS_DIR
    )
    resolved_community_path = (
        os.environ.get("TASK_SKILL_ROUTER_COMMUNITY")
        or os.environ.get("SKILL_ROUTER_COMMUNITY")
        or community_path
        or config.get("community_mapping")
        or DEFAULT_COMMUNITY_PATH
    )

    mode_overrides = config.get("mode_overrides", {})
    if not isinstance(mode_overrides, dict):
        mode_overrides = {}
    preferred_skills = set(as_list(config.get("preferred_skills")))
    try:
        max_matches = max(1, int(config.get("max_matches", MAX_MATCHES)))
    except (TypeError, ValueError):
        max_matches = MAX_MATCHES
    try:
        threshold = float(config.get("confidence_threshold", CONFIDENCE_THRESHOLD))
    except (TypeError, ValueError):
        threshold = CONFIDENCE_THRESHOLD

    # Discover skills
    skills = discover_skills(
        as_list(resolved_skills_dirs)
        if isinstance(resolved_skills_dirs, list)
        else str(resolved_skills_dirs)
    )
    community = load_community_mapping(str(resolved_community_path))

    community_only_skills: dict[str, dict[str, Any]] = {}
    for name, mapping in community.items():
        desc = str(mapping.get("description", "") or "")
        tags = as_list(mapping.get("tags"))
        command = str(mapping.get("command", "") or "")
        mode = str(mapping.get("mode", "") or "")
        install_hint = str(mapping.get("install", "") or "")
        if name in skills:
            skills[name]["community_description"] = desc
            skills[name]["community_tags"] = tags
            skills[name]["community_command"] = command
            skills[name]["community_mode"] = mode
            skills[name]["community_install"] = install_hint
        else:
            community_only_skills[name] = {
                "description": desc,
                "tags": tags,
                "command": command,
                "mode": mode,
                "install": install_hint,
            }

    # Build TF-IDF index
    index = TfidfIndex()

    # Index all discovered skills
    for skill_name, meta in skills.items():
        text = skill_index_text(skill_name, meta)
        index.add(skill_name, text)

    # Index community-only skills when the user has not installed the skill.
    for name, mapping in community_only_skills.items():
        text = f"{name} {mapping['description']} {' '.join(mapping['tags'])}"
        index.add(f"_community_{name}", text)

    index.build()

    # Search
    results = index.search(task, top_k=max_matches * 4)

    # Build response
    high_risk = is_high_risk(task)
    matches: list[dict[str, Any]] = []
    missing_skills: list[dict[str, Any]] = []

    for doc_id, confidence in results:
        is_community = doc_id.startswith("_community_")
        if is_community:
            skill_name = doc_id.removeprefix("_community_")
            cs = community_only_skills.get(skill_name, {})
            path = ""
            installed = False
            mode = select_mode(
                task,
                skill_name,
                confidence,
                mode_overrides,
                suggested_mode=str(cs.get("mode", "") or "recommend"),
            )
            reason = "community mapping"
            command = str(cs.get("command", "") or "")
            commands = [command] if command else []
            install_hint = str(cs.get("install", "") or "")
        else:
            if doc_id not in skills:
                continue
            meta = skills[doc_id]
            skill_name = meta["name"]
            path = meta["path"]
            installed = True
            mode = select_mode(
                task,
                skill_name,
                confidence,
                mode_overrides,
                suggested_mode=str(meta.get("community_mode", "") or ""),
            )
            reason = (
                "TF-IDF match on skill metadata + community mapping"
                if meta.get("community_description") or meta.get("community_tags")
                else "TF-IDF match on skill metadata"
            )
            command = str(meta.get("community_command", "") or "")
            commands = [command] if command else []
            install_hint = str(meta.get("community_install", "") or "")

        if skill_name in preferred_skills:
            confidence *= 1.05

        if confidence < threshold:
            continue

        if high_risk and mode != "recommend":
            mode = "recommend"

        match = {
            "skill": skill_name,
            "installed": installed,
            "path": path,
            "confidence": round(confidence, 3),
            "mode": mode,
            "reason": reason,
            "commands": commands,
        }
        if not installed:
            match["install_hint"] = (
                install_hint
                or f"Install the '{skill_name}' skill into one of skills_dirs, then rerun task-skill-router."
            )
            missing_skills.append({
                "skill": skill_name,
                "confidence": match["confidence"],
                "install_hint": match["install_hint"],
            })
        matches.append(match)

    # Sort by confidence, limit
    matches.sort(key=lambda m: m["confidence"], reverse=True)
    matches = matches[:max_matches]

    result: dict[str, Any] = {
        "task": task,
        "num_skills_discovered": len(skills),
        "num_community_mappings": len(community),
        "num_community_only_mappings": len(community_only_skills),
        "skills_dirs": [
            str(Path(path).expanduser())
            for path in (
                as_list(resolved_skills_dirs)
                if isinstance(resolved_skills_dirs, list)
                else str(resolved_skills_dirs).split(os.pathsep)
            )
            if path
        ],
        "config_path": str(Path(str(resolved_config_path)).expanduser()),
        "community_path": (
            str(Path(str(resolved_community_path)).expanduser())
            if resolved_community_path
            else ""
        ),
        "confidence_threshold": threshold,
        "matches": matches,
        "missing_skills": missing_skills,
        "high_risk": high_risk,
        "no_match_reason": None,
    }

    if not matches:
        result["no_match_reason"] = (
            "No skill matched this task with sufficient confidence. "
            "Try rephrasing your task, or add keywords to your SKILL.md descriptions."
        )
        # Include all discovered skills as hints
        result["available_skills"] = sorted(skills.keys())

    return result


def recommend_batch(tasks: list[str]) -> dict[str, Any]:
    """Route already-decomposed execution tasks one by one."""
    results = [recommend(task) for task in tasks if task.strip()]
    missing_by_skill: dict[str, dict[str, Any]] = {}
    for result in results:
        for missing in result.get("missing_skills", []):
            name = missing["skill"]
            current = missing_by_skill.get(name)
            if current is None or missing["confidence"] > current["confidence"]:
                missing_by_skill[name] = missing

    return {
        "batch": True,
        "num_tasks": len(results),
        "results": results,
        "num_without_matches": sum(1 for result in results if not result["matches"]),
        "missing_skills": sorted(
            missing_by_skill.values(),
            key=lambda item: item["confidence"],
            reverse=True,
        ),
    }


# ──────────────────────────────────────────────
#  CLI entry point
# ──────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Route decomposed terminal-agent tasks to matching SKILL.md workflows."
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Read one decomposed task per stdin line and route each task.",
    )
    parser.add_argument("task", nargs="*", help="Task text to route.")
    args = parser.parse_args()

    if args.batch:
        stdin_tasks = [line.strip() for line in sys.stdin if line.strip()]
        cli_task = " ".join(args.task).strip()
        tasks = stdin_tasks or ([cli_task] if cli_task else [])
        if not tasks:
            print(json.dumps({"error": "No tasks provided"}, ensure_ascii=False))
            sys.exit(1)

        result = recommend_batch(tasks)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result["num_without_matches"] == result["num_tasks"]:
            sys.exit(1)
        return

    if args.task:
        task = " ".join(args.task)
    else:
        task = sys.stdin.read().strip()

    if not task:
        print(json.dumps({"error": "No task provided"}, ensure_ascii=False))
        sys.exit(1)

    result = recommend(task)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if not result["matches"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
