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
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

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
DEFAULT_AUDIT_LOG_PATH = "~/.task-skill-router/audit/events.jsonl"
MAX_MATCHES = 5
CONFIDENCE_THRESHOLD = 0.12
VALID_MODES = {"auto-load", "auto-run", "recommend"}
VALID_JUDGMENTS = {"hit", "miss", "partial", "unknown"}

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
        try:
            data = _yaml.safe_load(text) or {}
        except Exception:
            data = parse_simple_yaml(text)
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


def frontmatter_plain_description(text: str) -> str:
    """Convert invalid SKILL.md frontmatter into searchable fallback text."""
    lines: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped == "---":
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("name:"):
            continue
        if stripped.startswith("description:"):
            value = stripped.split(":", 1)[1].strip()
            if value:
                lines.append(value.strip("'\""))
            continue
        lines.append(stripped)
    return " ".join(lines)


def load_skill_frontmatter(text: str) -> dict[str, Any]:
    """Load one SKILL.md frontmatter block without letting invalid YAML crash discovery."""
    if _yaml is not None:
        try:
            data = _yaml.safe_load(text) or {}
        except Exception:
            data = parse_simple_yaml(text)
            data["description"] = frontmatter_plain_description(text)
    else:
        data = parse_simple_yaml(text)
    if not isinstance(data, dict):
        return {"description": frontmatter_plain_description(text)}
    if not data.get("description"):
        data["description"] = frontmatter_plain_description(text)
    return data


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

DEFAULT_SYNONYMS = {
    "test": ["測試", "测试", "單元測試", "单元测试", "寫測試", "写测试", "測試失敗", "测试失败"],
    "build": ["建置", "構建", "构建", "編譯", "编译", "打包"],
    "compile": ["編譯", "编译"],
    "review": ["審查", "审查", "代碼審查", "代码审查", "檢查代碼", "检查代码", "審計", "审计"],
    "audit": ["審計", "审计", "審查", "审查"],
    "remember": ["記住", "记住", "記憶", "记忆", "記錄", "记录", "記下", "记下", "偏好"],
    "memory": ["記憶", "记忆", "偏好"],
    "workflow": ["工作流", "多 agent", "多Agent", "並行", "并行", "協作", "协作"],
    "parallel": ["並行", "并行", "多 agent", "多Agent"],
    "refactor": ["重構", "重构", "重整", "整理代碼", "整理代码"],
    "auth": ["登入", "登录", "登錄", "認證", "认证", "授權", "授权"],
    "login": ["登入", "登录", "登錄"],
    "debug": ["除錯", "调试", "偵錯", "排錯", "排错", "故障", "錯誤", "错误"],
    "ui": ["界面", "介面", "按鈕", "按钮", "元件", "组件"],
    "button": ["按鈕", "按钮"],
    "swiftui": ["swiftui"],
    "docs": ["文檔", "文档", "文件", "說明", "说明", "README", "readme"],
    "route": ["路由", "匹配", "推薦", "推荐"],
    "skill": ["技能"],
    "preference": ["偏好"],
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
    tokens = re.findall(r"[a-z][a-z0-9]{1,}|[\u4e00-\u9fff]{1,6}", text)
    return [normalize_token(token) for token in tokens]


def load_synonyms(config: dict[str, Any] | None = None) -> dict[str, list[str]]:
    """Merge built-in and user-configured synonym mappings."""
    synonyms: dict[str, list[str]] = {
        key: list(value)
        for key, value in DEFAULT_SYNONYMS.items()
    }
    if config:
        configured = config.get("synonyms", {})
        if isinstance(configured, dict):
            for canonical, values in configured.items():
                key = normalize_token(str(canonical).lower())
                synonyms.setdefault(key, [])
                for value in as_list(values):
                    if value not in synonyms[key]:
                        synonyms[key].append(value)
    return synonyms


def expand_with_synonyms(text: str, synonyms: dict[str, list[str]]) -> str:
    """Append canonical terms for any configured synonym phrase found in text."""
    lowered = text.lower()
    extra: list[str] = []
    for canonical, values in synonyms.items():
        canonical_token = normalize_token(str(canonical).lower())
        if canonical_token in tokenize(text):
            extra.append(canonical_token)
        for value in values:
            value_text = str(value).strip()
            if value_text and value_text.lower() in lowered:
                extra.append(canonical_token)
                break
    return " ".join([text, *extra])


class TfidfIndex:
    """Minimal pure-Python TF-IDF vectorizer and index."""

    def __init__(self):
        self.doc_vectors: list[tuple[str, Counter]] = []  # (doc_id, tf_counter)
        self.idf: dict[str, float] = {}
        self.num_docs = 0
        self._built = False
        self.synonyms: dict[str, list[str]] = {}

    def add(self, doc_id: str, text: str, synonyms: dict[str, list[str]] | None = None) -> None:
        expanded_text = expand_with_synonyms(text, synonyms or self.synonyms)
        tokens = tokenize(expanded_text)
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

    def search(
        self,
        query: str,
        top_k: int = 10,
        synonyms: dict[str, list[str]] | None = None,
    ) -> list[tuple[str, float]]:
        if not self._built:
            self.build()
        if self.num_docs == 0:
            return []

        expanded_query = expand_with_synonyms(query, synonyms or self.synonyms)
        q_tokens = tokenize(expanded_query)
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

            meta = load_skill_frontmatter(m.group(1))
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


def dedupe_missing_skills(missing_skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the highest-confidence missing-skill hint for each skill."""
    by_skill: dict[str, dict[str, Any]] = {}
    for missing in missing_skills:
        name = str(missing.get("skill", ""))
        if not name:
            continue
        current = by_skill.get(name)
        if current is None or float(missing.get("confidence", 0)) > float(current.get("confidence", 0)):
            by_skill[name] = missing
    return sorted(
        by_skill.values(),
        key=lambda item: float(item.get("confidence", 0)),
        reverse=True,
    )


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
#  Recommendation audit and hit-rate statistics
# ──────────────────────────────────────────────

def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def audit_log_path(path: str | None = None) -> Path:
    resolved = (
        path
        or os.environ.get("TASK_SKILL_ROUTER_AUDIT_LOG")
        or os.environ.get("SKILL_ROUTER_AUDIT_LOG")
        or DEFAULT_AUDIT_LOG_PATH
    )
    return Path(resolved).expanduser()


def append_jsonl(path: str | Path, event: dict[str, Any]) -> None:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
        fh.write("\n")


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path).expanduser()
    if not p.is_file():
        return []
    events: list[dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
    return events


def recommendation_event_id(result: dict[str, Any]) -> str:
    payload = {
        "task": result.get("task", ""),
        "matches": [
            {
                "skill": match.get("skill", ""),
                "installed": match.get("installed", False),
                "confidence": match.get("confidence", 0),
            }
            for match in result.get("matches", [])[:5]
        ],
    }
    digest = hashlib.sha1(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    return f"rec_{digest}_{uuid4().hex[:8]}"


def compact_recommendation_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "task": result.get("task", ""),
        "top_skill": result["matches"][0]["skill"] if result.get("matches") else "",
        "matches": [
            {
                "skill": match.get("skill", ""),
                "installed": match.get("installed", False),
                "confidence": match.get("confidence", 0),
                "mode": match.get("mode", ""),
                "reason": match.get("reason", ""),
            }
            for match in result.get("matches", [])
        ],
        "missing_skills": result.get("missing_skills", []),
        "high_risk": result.get("high_risk", False),
        "no_match_reason": result.get("no_match_reason"),
    }


def record_recommendation(result: dict[str, Any], path: str | None = None) -> str:
    event_id = recommendation_event_id(result)
    result["audit_event_id"] = event_id
    event = {
        "type": "recommendation",
        "event_id": event_id,
        "created_at": utc_now(),
        "recommendation": compact_recommendation_result(result),
    }
    append_jsonl(audit_log_path(path), event)
    return event_id


def record_review(
    event_id: str,
    judgment: str,
    evaluator: str,
    notes: str = "",
    correct_skill: str = "",
    path: str | None = None,
) -> dict[str, Any]:
    judgment = judgment.lower().strip()
    if judgment not in VALID_JUDGMENTS:
        raise ValueError(f"judgment must be one of: {', '.join(sorted(VALID_JUDGMENTS))}")
    event = {
        "type": "review",
        "event_id": event_id,
        "created_at": utc_now(),
        "judgment": judgment,
        "evaluator": evaluator or "unknown",
        "correct_skill": correct_skill,
        "notes": notes,
    }
    append_jsonl(audit_log_path(path), event)
    return event


def audit_snapshot(path: str | None = None) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for event in read_jsonl(audit_log_path(path)):
        event_type = event.get("type")
        event_id = str(event.get("event_id", ""))
        if not event_id:
            continue
        if event_type == "recommendation":
            snapshot.setdefault(event_id, {})["recommendation"] = event
        elif event_type == "review":
            snapshot.setdefault(event_id, {}).setdefault("reviews", []).append(event)
    return snapshot


def pending_reviews(path: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event_id, item in audit_snapshot(path).items():
        if item.get("reviews"):
            continue
        rec_event = item.get("recommendation")
        if not rec_event:
            continue
        rec = rec_event.get("recommendation", {})
        rows.append({
            "event_id": event_id,
            "created_at": rec_event.get("created_at", ""),
            "task": rec.get("task", ""),
            "top_skill": rec.get("top_skill", ""),
            "matches": rec.get("matches", []),
            "missing_skills": rec.get("missing_skills", []),
        })
    rows.sort(key=lambda row: row["created_at"])
    return rows[:max(1, limit)]


def audit_stats(path: str | None = None) -> dict[str, Any]:
    snapshot = audit_snapshot(path)
    reviewed: list[dict[str, Any]] = []
    pending = 0
    for event_id, item in snapshot.items():
        rec_event = item.get("recommendation")
        if not rec_event:
            continue
        reviews = item.get("reviews") or []
        if not reviews:
            pending += 1
            continue
        latest_review = sorted(reviews, key=lambda event: event.get("created_at", ""))[-1]
        reviewed.append({
            "event_id": event_id,
            "recommendation": rec_event.get("recommendation", {}),
            "review": latest_review,
        })

    counts = {judgment: 0 for judgment in sorted(VALID_JUDGMENTS)}
    by_skill: dict[str, dict[str, Any]] = {}
    by_evaluator: dict[str, dict[str, Any]] = {}
    for row in reviewed:
        judgment = row["review"].get("judgment", "unknown")
        if judgment not in counts:
            judgment = "unknown"
        counts[judgment] += 1
        top_skill = row["recommendation"].get("top_skill", "") or "(none)"
        evaluator = row["review"].get("evaluator", "unknown") or "unknown"
        for bucket, key in ((by_skill, top_skill), (by_evaluator, evaluator)):
            bucket.setdefault(key, {"total": 0, "hit": 0, "partial": 0, "miss": 0, "unknown": 0})
            bucket[key]["total"] += 1
            bucket[key][judgment] += 1

    reviewed_count = len(reviewed)
    scored_count = counts["hit"] + counts["miss"] + counts["partial"]
    full_hit_rate = counts["hit"] / scored_count if scored_count else None
    partial_credit_rate = (
        (counts["hit"] + 0.5 * counts["partial"]) / scored_count
        if scored_count
        else None
    )

    return {
        "audit_log": str(audit_log_path(path)),
        "recommendations": sum(1 for item in snapshot.values() if item.get("recommendation")),
        "reviewed": reviewed_count,
        "pending": pending,
        "counts": counts,
        "full_hit_rate": round(full_hit_rate, 4) if full_hit_rate is not None else None,
        "partial_credit_hit_rate": (
            round(partial_credit_rate, 4)
            if partial_credit_rate is not None
            else None
        ),
        "by_skill": by_skill,
        "by_evaluator": by_evaluator,
    }


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
    synonyms = load_synonyms(config)
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
    index.synonyms = synonyms

    # Index all discovered skills
    for skill_name, meta in skills.items():
        text = skill_index_text(skill_name, meta)
        index.add(skill_name, text, synonyms)

    # Index community-only skills when the user has not installed the skill.
    for name, mapping in community_only_skills.items():
        text = f"{name} {mapping['description']} {' '.join(mapping['tags'])}"
        index.add(f"_community_{name}", text, synonyms)

    index.build()

    # Search
    results = index.search(task, top_k=max_matches * 4, synonyms=synonyms)

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

    result["missing_skills"] = dedupe_missing_skills(result["missing_skills"])

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


def record_batch_recommendations(result: dict[str, Any], path: str | None = None) -> list[str]:
    event_ids: list[str] = []
    for item in result.get("results", []):
        if isinstance(item, dict):
            event_ids.append(record_recommendation(item, path))
    result["audit_event_ids"] = event_ids
    return event_ids


# ──────────────────────────────────────────────
#  CLI entry point
# ──────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Route decomposed terminal-agent tasks to matching SKILL.md workflows."
    )
    parser.add_argument(
        "--audit-log",
        help="Path to recommendation audit JSONL. Defaults to ~/.task-skill-router/audit/events.jsonl.",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="Record recommendation events for later hit-rate review.",
    )
    parser.add_argument(
        "--pending-reviews",
        action="store_true",
        help="Print recommendations that do not yet have hit-rate reviews.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Limit rows returned by --pending-reviews.",
    )
    parser.add_argument(
        "--review",
        metavar="EVENT_ID",
        help="Append a review judgment for a recorded recommendation event.",
    )
    parser.add_argument(
        "--judgment",
        choices=sorted(VALID_JUDGMENTS),
        help="Review judgment for --review: hit, partial, miss, or unknown.",
    )
    parser.add_argument(
        "--evaluator",
        default="manual",
        help="Reviewer identity, e.g. user, skill:code-review, agent:planner, gpt-5.",
    )
    parser.add_argument(
        "--correct-skill",
        default="",
        help="Optional correct skill name when judgment is miss or partial.",
    )
    parser.add_argument(
        "--notes",
        default="",
        help="Optional short review notes.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print recommendation hit-rate statistics from the audit log.",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Read one decomposed task per stdin line and route each task.",
    )
    parser.add_argument("task", nargs="*", help="Task text to route.")
    args = parser.parse_args()

    if args.pending_reviews:
        print(json.dumps(
            {
                "audit_log": str(audit_log_path(args.audit_log)),
                "pending_reviews": pending_reviews(args.audit_log, args.limit),
            },
            indent=2,
            ensure_ascii=False,
        ))
        return

    if args.stats:
        print(json.dumps(audit_stats(args.audit_log), indent=2, ensure_ascii=False))
        return

    if args.review:
        if not args.judgment:
            print(json.dumps(
                {"error": "--judgment is required with --review"},
                ensure_ascii=False,
            ))
            sys.exit(1)
        try:
            event = record_review(
                args.review,
                args.judgment,
                args.evaluator,
                notes=args.notes,
                correct_skill=args.correct_skill,
                path=args.audit_log,
            )
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))
            sys.exit(1)
        print(json.dumps(event, indent=2, ensure_ascii=False))
        return

    if args.batch:
        stdin_tasks = [line.strip() for line in sys.stdin if line.strip()]
        cli_task = " ".join(args.task).strip()
        tasks = stdin_tasks or ([cli_task] if cli_task else [])
        if not tasks:
            print(json.dumps({"error": "No tasks provided"}, ensure_ascii=False))
            sys.exit(1)

        result = recommend_batch(tasks)
        if args.record:
            record_batch_recommendations(result, args.audit_log)
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
    if args.record:
        record_recommendation(result, args.audit_log)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if not result["matches"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
