import json
import os
import subprocess
import sys


env = os.environ.copy()
env["TASK_SKILL_ROUTER_CONFIG"] = "examples/demo-config.yaml"

proc = subprocess.run(
    [sys.executable, "task-skill-router.py", "--batch"],
    input=(
        "inspect failing tests and identify root cause\n"
        "update README docs\n"
        "search research papers for related work\n"
    ),
    capture_output=True,
    check=True,
    env=env,
    text=True,
)

data = json.loads(proc.stdout)
skills = [
    result["matches"][0]["skill"]
    for result in data["results"]
    if result.get("matches")
]
missing = [item["skill"] for item in data["missing_skills"]]

assert "systematic-debugging" in skills, skills
assert "docs" in skills, skills
assert "arxiv" in missing, missing
